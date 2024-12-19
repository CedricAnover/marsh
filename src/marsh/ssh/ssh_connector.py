from typing import Optional, Tuple

from fabric import Connection, Config

from marsh import Connector


class SshConnector(Connector):
    """
    SSH Connector built on top of the Fabric library for establishing and managing 
    SSH connections to remote hosts.

    Uses the `fabric.Connection` class to handle SSH connections, execute commands, 
    and return results.
    """
    def __init__(self, config: Optional[Config] = None):
        self._config = config

    def connect(self, *conn_args, **conn_kwargs) -> Connection:
        """
        Establishes an SSH connection to a remote host using the provided connection arguments.

        Args:
            *conn_args: Arguments to pass to the `fabric.Connection` constructor.
            **conn_kwargs: Keyword arguments to pass to the `fabric.Connection` constructor.

        Returns:
            Connection: A `fabric.Connection` instance representing the SSH connection.
        """
        if self._config:
            return Connection(*conn_args, config=self._config, **conn_kwargs)
        return Connection(*conn_args, **conn_kwargs)

    def disconnect(self, connection: Connection) -> None:
        """
        Closes the provided SSH `fabric.Connection`.

        Args:
            connection (Connection): The SSH `fabric.Connection` to close.
        """
        connection.close()

    def exec_cmd(self,
                 command: list[str],
                 connection: Connection,
                 encoding: str = "utf-8",
                 **run_kwargs
                 ) -> Tuple[bytes, bytes]:
        """
        Executes a command on the remote host and returns the stdout and stderr as byte-encoded strings.

        Args:
            command (list[str]): The command to execute on the remote host.
            connection (Connection): The SSH `fabric.Connection` to use for executing the command.
            encoding (str): The encoding to use for the output. Default is "utf-8".
            **run_kwargs: Additional arguments to pass to the `run` method of `fabric.Connection`.

        Returns:
            Tuple[bytes, bytes]: A tuple containing the byte-encoded stdout and stderr of the command execution.
        """
        # TODO: Add timeout to command.
        result = None
        try:
            command = " ".join(command)
            result = connection.run(command, hide=True, **run_kwargs)
            return result.stdout.encode(encoding), result.stderr.encode(encoding)
        except Exception as e:
            return b"", str(e).encode(encoding)
        finally:
            if result:
                self.disconnect(connection)
