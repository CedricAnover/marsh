from typing import Callable, Tuple, Any, Optional
from abc import ABCMeta, ABC, abstractmethod

# from invoke.exceptions import UnexpectedExit
# from fabric import Connection, Config


class Connector(ABC):
    @abstractmethod
    def connect(self, *args, **kwargs) -> Optional[Any]:
        pass

    @abstractmethod
    def disconnect(self, connection: Any, *args, **kwargs)  -> Optional[Any]:
        pass

    @abstractmethod
    def exec_cmd(self, command: list[str], connection: Any, *args, **kwargs) -> Tuple[bytes, bytes]:
        # TODO: Add timeout for running a remote command.
        pass


# class FabricConnector(Connector):
#     def __init__(self, fabric_config: Optional[Config] = None):
#         self._config = fabric_config

#     def connect(self, host: str, *conn_args, **conn_kwargs) -> Connection:
#         if self._config:
#             return Connection(host, *conn_args, config=self._config, **conn_kwargs)
#         return Connection(host, *conn_args, **conn_kwargs)

#     def disconnect(self, connection: Connection) -> None:
#         connection.close()

#     def exec_cmd(self, command: list[str], connection: Connection, **run_kwargs) -> Tuple[bytes, bytes]:
#         stdout = stderr = b""
#         result = None
#         try:
#             command = " ".join(command)
#             result = connection.run(command, hide=True, **run_kwargs)
#             return result.stdout.encode(), result.stderr.encode()
#         except UnexpectedExit as e:
#             return b"", str(e).encode()
#         finally:
#             self.disconnect(connection)
