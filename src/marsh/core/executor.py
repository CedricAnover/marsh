import textwrap
import pickle
import subprocess
from abc import abstractmethod, ABC
from typing import Callable, Tuple, Any

from ..utils.output_streams import suppress_output
from .command_grammar import CommandGrammar
from .connector import Connector


class Executor(ABC):
    """
    Abstract base class for command execution.

    This class defines a common interface for running commands, where subclasses implement 
    the `run` method to execute commands in specific environments (e.g., local, remote).
    """

    @abstractmethod
    def run(self, x_stdout: bytes, x_stderr: bytes, *args, **kwargs) -> Tuple[bytes, bytes]:
        """
        Abstract method to run a command.

        Args:
            x_stdout (bytes): Standard output from a previous command.
            x_stderr (bytes): Standard error from a previous command.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Tuple[bytes, bytes]: A tuple containing standard output and standard error.

        Raises:
            NotImplementedError: If the subclass does not override this method.
        """
        pass


class LocalCommandExecutor(Executor):
    """Executes commands locally as subprocesses."""

    def __init__(self,
                 command_grammar: CommandGrammar,
                 pipe_prev_stdout: bool = False,
                 timeout: float | None = None,
                 ):
        """
        Initializes a LocalCommandExecutor.

        Args:
            command_grammar (CommandGrammar): A CommandGrammar object to build the command.
            pipe_prev_stdout (bool, optional): Whether to pipe the previous standard output as input. Defaults to False.
            timeout (float | None, optional): Timeout for command execution in seconds. Defaults to None.
        """

        self.command_grammar = command_grammar  # Already parameterized the command grammar
        self.pipe_prev_stdout = pipe_prev_stdout  # (Unix) Pipe the previous STDOUT as STDIN for current command runner
        self.timeout = timeout

    @staticmethod
    def create_popen_with_pipe(command: list[str], *args, **kwargs) -> subprocess.Popen:
        """
        Creates a subprocess with pipes for stdin, stdout, and stderr.

        Args:
            command (list[str]): The command to execute as a list of strings.
            *args: Additional positional arguments for `subprocess.Popen`.
            **kwargs: Additional keyword arguments for `subprocess.Popen`.

        Returns:
            subprocess.Popen: A subprocess instance with pipes.
        """
        return subprocess.Popen(command, *args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                **kwargs)

    def run(self,
            x_stdout: bytes,
            x_stderr: bytes,
            *args,
            callback: Callable[[subprocess.Popen, bytes, bytes], Tuple[bytes, bytes]] = None,
            popen_args=(),
            popen_kwargs=None,
            **kwargs
            ) -> Tuple[bytes, bytes]:
        """
        Runs a command locally.

        Args:
            x_stdout (bytes): Standard output to pass to the command.
            x_stderr (bytes): Standard error to pass to the command.
            *args: Additional positional arguments.
            callback (Callable, optional): A custom callback function that takes subprocess.Popen, stdout, and stderr.
                This callback must return tuple[bytes, bytes] which represents the result.
            popen_args (tuple, optional): Arguments for `subprocess.Popen`. Defaults to ().
            popen_kwargs (dict, optional): Keyword arguments for `subprocess.Popen`. Defaults to None.
            **kwargs: Additional keyword arguments for `subprocess.Popen`.

        Returns:
            Tuple[bytes, bytes]: A tuple containing standard output and standard error.

        Raises:
            ValueError: If the provided callback does not return a tuple of bytes.
        """

        popen_kwargs = popen_kwargs or dict()

        # Build the Command as List of Strings
        command = self.command_grammar.build_cmd()

        # Create subprocess.Popen
        process = self.create_popen_with_pipe(command, *args, **kwargs)

        # Use the custom callback provided by user/client
        if callback:
            result = callback(process, x_stdout, x_stderr, *popen_args, **popen_kwargs)
            match result:
                # The `process.communicate(...)` must be invoked in the `callback` to return (stdout, stderr).
                case (stdout, stderr) if isinstance(stdout, bytes) and isinstance(stderr, bytes):
                    return stdout, stderr
                case _:
                    raise ValueError("Given callback must return tuple[bytes, bytes]")

        # Use the default procedure for running programs
        stdout, stderr = process.communicate(input=x_stdout,
                                             timeout=self.timeout) if self.pipe_prev_stdout else process.communicate(
            timeout=self.timeout)
        return stdout, stderr


class RemoteCommandExecutor(Executor):
    """
    Executes commands on remote systems via a connector interface.

    This class uses a `Connector` to establish a connection to a remote host
    and execute a command generated by a `CommandGrammar`. The command is sent
    to the remote system, and the standard output and error are retrieved.
    """

    def __init__(self, connector: Connector, command_grammar: CommandGrammar):
        """
        Initializes a RemoteCommandExecutor.

        Args:
            connector (Connector): An object responsible for managing the connection to the remote system.
            command_grammar (CommandGrammar): An object to build and format the command to be executed remotely.
        """
        self.connector = connector
        self.command_grammar = command_grammar

    def run(self,
            x_stdout: bytes,
            x_stderr: bytes,
            *build_cmd_args,
            conn_args=(),
            exec_cmd_args=(),
            exec_cmd_kwargs=None,
            conn_kwargs=None,
            **build_cmd_kwargs,
            ) -> Tuple[bytes, bytes]:
        """
        Runs a command on a remote system and retrieves its output.

        This method connects to a remote host using the provided `Connector`, runs the command
        generated by `CommandGrammar`, and returns the standard output and standard error.

        Args:
            x_stdout (bytes): Standard output to pass as input, if required by the command.
            x_stderr (bytes): Standard error to pass as input, if required by the command.
            *build_cmd_args: Additional arguments passed to `CommandGrammar.build_cmd`.
            conn_args (tuple, optional): Positional arguments for the `Connector.connect` method.
            exec_cmd_args (tuple, optional): Positional arguments for the `Connector.exec_cmd` method.
            exec_cmd_kwargs (dict, optional): Keyword arguments for `Connector.exec_cmd`. Defaults to None.
            conn_kwargs (dict, optional): Keyword arguments for the `Connector.connect` method. Defaults to None.
            **build_cmd_kwargs: Additional keyword arguments for `CommandGrammar.build_cmd`.

        Returns:
            Tuple[bytes, bytes]: A tuple containing:
                - stdout (bytes): The standard output from the remote command execution.
                - stderr (bytes): The standard error from the remote command execution.
        """
        exec_cmd_kwargs = exec_cmd_kwargs or dict()
        conn_kwargs = conn_kwargs or dict()
        connection = None
        # TODO: Enhance and include Pipes.
        try:
            connection = self.connector.connect(*conn_args, **conn_kwargs)
            stdout, stderr = self.connector.exec_cmd(
                self.command_grammar.build_cmd(*build_cmd_args, **build_cmd_kwargs),
                connection,
                *exec_cmd_args,
                **exec_cmd_kwargs
            )
            return stdout, stderr
        except Exception as e:
            return b"", str(e).encode()
        finally:
            self.connector.disconnect(connection)


class PythonExecutor(Executor):
    """
    Runs Python code in the specified mode ('eval' or 'exec') within a given namespace.

    The PythonExecutor class allows for the execution or evaluation of Python code in a specific namespace,
    with optional support for serializing results via pickle.
    """

    def __init__(self,
                 py_code: str,
                 mode: str = "eval",
                 namespace: dict | None = None,
                 use_pickle: bool = False,
                 ):
        """
        Initializes a PythonExecutor.

        Args:
            py_code (str): The Python code to execute or evaluate. This should be a valid python expression for `eval()`,
                or a valid python statement(s) for `exec()`.
            mode (str, optional): The mode for executing the code, either 'eval' (default) or 'exec'.
            namespace (dict, optional): The namespace in which to execute the code. Defaults to None.
                The namespace would contain "x_stdout" and "x_stderr" for both `eval` and `exec` modes. This is for
                referencing the previous results. The result of `exec` mode can be stored in a variable `exec_result`
                to be referenced by the next command runner. If this is not specified, the value of `stdout` will be
                'None'.
            use_pickle (bool, optional): Whether to pickle the result. Defaults to False.

        Raises:
            ValueError: If the mode is not 'eval' or 'exec', or if the Python code is empty.
        """
        if mode not in ["eval", "exec"]:
            raise ValueError("`mode` must be 'eval' or 'exec'.")

        if not py_code.strip():
            raise ValueError("Python code is empty.")

        self._mode = mode
        self._namespace = namespace or {}
        self._py_code = textwrap.dedent(py_code)
        self._use_pickle = use_pickle

    def run(self,
            x_stdout: bytes,
            x_stderr: bytes,
            encoding: str = "utf-8",
            pickle_kwargs: dict | None = None,
            **kwargs
            ) -> Tuple[bytes, bytes]:
        """
        Executes or evaluates Python code in the provided namespace with the given standard output and error.

        Args:
            x_stdout (bytes): The standard output stream to pass to the code.
            x_stderr (bytes): The standard error stream to pass to the code.
            encoding (str, optional): The encoding for the result. Defaults to "utf-8".
            pickle_kwargs (dict | None, optional): Additional keyword arguments for pickle dumps. Defaults to None.
            **kwargs (dict, optional): Additional keyword arguments for either `eval` or `exec`.

        Returns:
            Tuple[bytes, bytes]: A tuple containing:
                - The result of the execution or evaluation as a byte string.
                - An empty byte string if no error occurs, or an error message in byte string form.
        """

        pickle_kwargs = pickle_kwargs or {}

        # Inject x_stdout and x_stderr into the namespace
        self._namespace["x_stdout"] = x_stdout
        self._namespace["x_stderr"] = x_stderr

        # Use the context manager to suppress stdout and stderr during execution
        with suppress_output():
            try:
                if self._mode == "exec":
                    self._namespace["exec_result"] = None  # To store results for code.
                    exec(self._py_code, self._namespace, **kwargs)
                    result = self._namespace["exec_result"]
                else:
                    result = eval(self._py_code, self._namespace, **kwargs)

                if self._use_pickle:
                    return pickle.dumps(result, **pickle_kwargs), b""

                return str(result).encode(encoding), b""

            except Exception as err:
                return b"", str(err).encode(encoding)


__all__ = (
    "Executor",
    "LocalCommandExecutor",
    "RemoteCommandExecutor",
    "PythonExecutor",
)
