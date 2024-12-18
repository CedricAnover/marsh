from typing import Optional, Tuple

from fabric import Connection, Config

from marsh import Connector


class SshConnector(Connector):
    """
    SSH Connector built on top of fabric (https://www.fabfile.org/).
    """
    def __init__(self, config: Optional[Config] = None):
        self._config = config

    def connect(self, host: str, *conn_args, **conn_kwargs) -> Connection:
        if self._config:
            return Connection(host, config=self._config, *conn_args, **conn_kwargs)
        return Connection(host, *conn_args, **conn_kwargs)

    def disconnect(self, connection: Connection, *args, **kwargs) -> None:
        connection.close()

    def exec_cmd(self,
                 command: list[str],
                 connection: Connection,
                 encoding: str = "utf-8",
                 **run_kwargs
                 ) -> Tuple[bytes, bytes]:
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
