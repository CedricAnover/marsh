import subprocess
from abc import abstractmethod, ABC
from typing import Callable, Tuple, Any

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
    """
    Base class for executing commands on remote systems.

    The `RemoteCommandExecutor` serves as an abstract base class that provides the interface
    for executing commands in remote environments. It manages the lifecycle of a remote connection
    (establishment, execution, and cleanup) while delegating the implementation details of 
    connection setup and command execution to its subclasses.

    Subclasses should override:
      - `establish_connection`: To set up the connection to the remote system.
      - `execute_command`: To define how commands are executed on the remote system.
      - `close_connection`: (Optional) To handle cleanup and closing of the remote connection.
    """

    @abstractmethod
    def establish_connection(self, *args, **kwargs) -> Any | None:
        """
        Hook for subclasses to implement the logic for establishing a remote connection.

        This method is called before executing the command. Subclasses may return a connection 
        object that will be passed to `execute_command` and `close_connection`.

        Args:
            *args: Additional positional arguments for connection setup.
            **kwargs: Additional keyword arguments for connection setup.

        Returns:
            Any | None: A connection object (e.g., SSH client, API session) or `None` 
                        if no connection is required.
        """
        pass

    def close_connection(self, connection: Any, *args, **kwargs) -> None:
        """
        Hook for subclasses to implement connection cleanup logic.

        This method is called automatically after command execution to ensure resources 
        are properly released. The implementation of `close_connection` can be optional
        if the subclass would use context manager for establishing a remote connection.

        Args:
            connection (Any): The connection object returned by `establish_connection`.
            *args: Additional positional arguments for connection cleanup.
            **kwargs: Additional keyword arguments for connection cleanup.
        """
        pass  # Default: No connection cleanup needed.

    @abstractmethod
    def execute_command(self, connection: Any, x_stdout: bytes, x_stderr: bytes, *args, **kwargs) -> tuple[bytes, bytes]:
        """
        Abstract method to execute a command in the remote environment.

        Subclasses must implement this method to define how commands are run remotely.
        This is due to the fact that most external packages such as Paramiko or Fabric
        would have a run or execute method attached to a connection object.

        Args:
            connection (Any): The connection object returned by `establish_connection`.
            x_stdout (bytes): Standard output from a previous command runner.
            x_stderr (bytes): Standard error from a previous command runner.
            *args: Additional positional arguments for the command execution.
            **kwargs: Additional keyword arguments for the command execution.

        Returns:
            tuple[bytes, bytes]: A tuple containing the standard output and standard error 
                                 from the executed command.

        Raises:
            NotImplementedError: If not implemented in a subclass.
        """
        pass

    def run(self, x_stdout: bytes, x_stderr: bytes, *args, **kwargs) -> tuple[bytes, bytes]:
        """
        Executes a command remotely, managing connection lifecycle.

        This method follows a sequence of steps:
            1. Calls `establish_connection` to set up the remote connection.
            2. Passes the connection to `execute_command` to run the command.
            3. Ensures `close_connection` is invoked for cleanup, even if execution fails.

        Args:
            x_stdout (bytes): Standard output to pass to the command.
            x_stderr (bytes): Standard error to pass to the command.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            tuple[bytes, bytes]: A tuple containing the standard output and standard error 
                                 from the executed command.
        """
        connection = None
        try:
            # Establish connection if needed
            connection = self.establish_connection(*args, **kwargs)
            stdout, stderr = self.execute_command(connection, x_stdout, x_stderr, *args, **kwargs)
            return stdout, stderr
        finally:
            # Ensure connection cleanup
            self.close_connection(connection, *args, **kwargs)


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
