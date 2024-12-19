from typing import Callable

from fabric import Config

from marsh import RemoteCommandExecutor
from .ssh_connector import SshConnector
from .ssh_command_grammar import SshCommandGrammar


class SshFactory:
    def __init__(self,
                 fabric_config: Config | None = None,
                 connection_args: tuple = (),
                 connection_kwargs: dict | None = None,
                 ):
        self._config = fabric_config
        self._conn_args = connection_args
        self._conn_kwargs = connection_kwargs or dict()

    def create_command_grammar(self, *args, **kwargs) -> SshCommandGrammar:
        return SshCommandGrammar(*args, **kwargs)

    def create_connector(self) -> SshConnector:
        return SshConnector(config=self._config)

    def create_cmd_runner(self, commands: list[str], pipe_prev_stdout: bool = False) -> Callable[[bytes, bytes], tuple[bytes, bytes]]:
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
        chained_commands = " && ".join(commands)  # Example: command1 && command2 && command3
        return self.create_cmd_runner([chained_commands], *args, **kwargs)
