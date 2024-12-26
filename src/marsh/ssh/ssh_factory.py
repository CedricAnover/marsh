from typing import Callable

from fabric import Config

from marsh import RemoteCommandExecutor
from .ssh_connector import SshConnector
from .ssh_command_grammar import SshCommandGrammar


class SshFactory:
    """
    Factory class for creating Marsh SSH components including connectors, command grammars,
    and command runners for managing remote command execution.
    """
    def __init__(self,
                 fabric_config: Config | None = None,
                 connection_args: tuple = (),
                 connection_kwargs: dict | None = None,
                 ):
        self._config = fabric_config
        self._conn_args = connection_args
        self._conn_kwargs = connection_kwargs or dict()

    def create_command_grammar(self, *args, **kwargs) -> SshCommandGrammar:
        """
        Creates an instance of `SshCommandGrammar` for constructing SSH commands.

        Args:
            *args: Arguments to pass to the `SshCommandGrammar` constructor.
            **kwargs: Keyword arguments to pass to the `SshCommandGrammar` constructor.

        Returns:
            SshCommandGrammar: An instance of `SshCommandGrammar` initialized with the provided arguments.
        """
        return SshCommandGrammar(*args, **kwargs)

    def create_connector(self) -> SshConnector:
        """
        Creates an instance of `SshConnector` for managing SSH connections.

        Returns:
            SshConnector: An instance of `SshConnector` initialized with `fabric.Config`
            object passed from `SshFactory` constructor.
        """
        return SshConnector(config=self._config)

    def create_cmd_runner(self, commands: list[str], pipe_prev_stdout: bool = False) -> Callable[[bytes, bytes], tuple[bytes, bytes]]:
        """
        Creates a command runner that executes a list of commands over SSH.

        The runner handles the execution of the specified commands and optionally pipes
        the stdout of the previous command to the next one.

        Args:
            commands (list[str]): A list of commands to execute on the remote host.
            pipe_prev_stdout (bool): Whether to pipe the stdout of the previous command to the next. Default is False.

        Returns:
            Callable[[bytes, bytes], tuple[bytes, bytes]]: A function that executes the commands and returns
            the stdout and stderr as byte-encoded strings.
        """
        connector = self.create_connector()
        command_grammar = self.create_command_grammar()
        remote_cmd_executor = RemoteCommandExecutor(connector, command_grammar)
        def cmd_runner(x_stdout: bytes, x_stderr: bytes) -> tuple[bytes, bytes]:
            return remote_cmd_executor.run(
                x_stdout,
                x_stderr,
                commands,
                conn_args=self._conn_args,
                conn_kwargs=self._conn_kwargs,
                prev_stdout=x_stdout if pipe_prev_stdout else None,
            )
        return cmd_runner

    def create_chained_cmd_runner(self, commands: list[str], *args, **kwargs) -> Callable[[bytes, bytes], tuple[bytes, bytes]]:
        """
        Creates a command runner that executes a series of chained commands over SSH.

        The commands will be joined together with '&&', ensuring that each command is only executed if
        the previous one succeeds.

        Args:
            commands (list[str]): A list of commands to execute on the remote host.
            *args: Arguments to pass to `SshFactory.create_cmd_runner`.
            **kwargs: Keyword arguments to pass to `SshFactory.create_cmd_runner`.

        Returns:
            Callable[[bytes, bytes], tuple[bytes, bytes]]: A function that executes the chained commands and returns
            the stdout and stderr as byte-encoded strings.
        """
        chained_commands = " && ".join(commands)  # Example: command1 && command2 && command3
        return self.create_cmd_runner([chained_commands], *args, **kwargs)