import subprocess
from abc import abstractmethod, ABC
from typing import Callable, Tuple, Any

from .connector import Connector
from .command_grammar import CommandGrammar


class Executor(ABC):
    """
    Abstract base class for command execution.

    This class defines a common interface for running commands, where subclasses implement 
    the `run` method to execute commands in specific environments (e.g., local, remote).
    """

    @abstractmethod
    def run(self, x_stdout: bytes, x_stderr: bytes, *args, **kwargs) -> tuple[bytes, bytes]:
        """
        Abstract method to run a command.

        Args:
            x_stdout (bytes): Standard output from a previous command.
            x_stderr (bytes): Standard error from a previous command.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            tuple[bytes, bytes]: A tuple containing standard output and standard error.

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
        return subprocess.Popen(command, *args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)

    def run(self,
            x_stdout: bytes,
            x_stderr: bytes,
            *args,
            callback: Callable[[subprocess.Popen, bytes, bytes], Tuple[bytes, bytes]] = None,
            popen_args=(),
            popen_kwargs=None,
            **kwargs
            ) -> tuple[bytes, bytes]:
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
            tuple[bytes, bytes]: A tuple containing standard output and standard error.

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
        stdout, stderr = process.communicate(input=x_stdout, timeout=self.timeout) if self.pipe_prev_stdout else process.communicate(timeout=self.timeout)
        return stdout, stderr


# TODO: Add tests for EnvCwdRelayExecutor class
class EnvCwdRelayExecutor(LocalCommandExecutor):
    """Extends LocalCommandExecutor to execute commands with a specified environment and working directory."""

    def __init__(self, env: dict[str, str], cwd: str, *args, **kwargs):
        """
        Initializes an EnvCwdRelayExecutor.

        Args:
            env (dict[str, str]): Environment variables for the command.
            cwd (str): Working directory for the command.
        """
        super().__init__(*args, **kwargs)
        self._env = env
        self._cwd = cwd

    def run(self, x_stdout, x_stderr, *args, **kwargs):
        """
        Executes the command with the specified environment and working directory.

        Args:
            x_stdout (bytes): Standard output to pass to the command.
            x_stderr (bytes): Standard error to pass to the command.
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            tuple[bytes, bytes]: A tuple containing standard output and standard error.
        """
        return super().run(x_stdout, x_stderr, *args, env=self._env, cwd=self._cwd, **kwargs)


class RemoteCommandExecutor(Executor):
    def __init__(self, connector: Connector, command_grammar: CommandGrammar):
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
            ) -> tuple[bytes, bytes]:
        exec_cmd_kwargs = exec_cmd_kwargs or dict()
        conn_kwargs = conn_kwargs or dict()
        connection = None
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


class DockerCommandExecutor(Executor):
    """Abstract class for executing commands in Docker containers."""
    # TODO: Implement Abstract Class and Interface for DockerCommandExecutor
    # This will use `docker` as the program of the CommandGrammar.
    # We may build this on top of Python-on-Whales (CLI Wrapper) or Docker Python SDK (direct to unix socket).
    def run(self, x_stdout, x_stderr, *args, **kwargs):
        raise NotImplementedError


class PythonExpressionExecutor(Executor):
    """Executes dynamic Python expressions using `eval`."""

    def __init__(self,
                 python_expr_fn: Callable[[bytes, bytes], str],
                 locals_=None,
                 globals_=None
                 ):
        self._python_expr_fn = python_expr_fn
        self._locals = locals_ or dict()
        self._globals = globals_ or dict()

    def run(self,
            x_stdout: bytes,
            x_stderr: bytes,
            *args, **kwargs
            ):
        try:
            # python_expr_fn :: (bytes, bytes, ...) => str
            result = eval(
                self._python_expr_fn(x_stdout, x_stderr, *args, **kwargs),
                self._globals,
                self._locals
            )
            return repr(result).encode("utf-8"), b""
        except Exception as e:
            return b"", repr(e).encode()


__all__ = (
    "Executor",
    "LocalCommandExecutor",
    "EnvCwdRelayExecutor",
    "RemoteCommandExecutor",
    "PythonExpressionExecutor",
    "DockerCommandExecutor"
)
