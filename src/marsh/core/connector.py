from typing import Optional, Tuple, Any
from abc import ABC, abstractmethod


class Connector(ABC):
    """
    Abstract base class for managing connections and executing commands on remote systems.

    The `Connector` class defines an interface for establishing, managing, and closing
    connections to remote systems, as well as executing commands on those systems.
    Subclasses must provide concrete implementations for connecting to a remote host,
    executing a command, and disconnecting from the host.

    Note:
        Subclasses of `Connector` are responsible for handling specific connection
        protocols, such as SSH, HTTP, or other custom communication mechanisms.
    """
    @abstractmethod
    def connect(self, *args, **kwargs) -> Optional[Any]:
        """
        Establishes a connection to a remote system.

        Args:
            *args: Positional arguments specific to the connection implementation.
            **kwargs: Keyword arguments for configuring the connection.

        Returns:
            Optional[Any]: A connection object or `None` if the connection fails.

        Raises:
            NotImplementedError: If not implemented in a subclass.
        """
        pass

    @abstractmethod
    def disconnect(self, connection: Any, *args, **kwargs)  -> Optional[Any]:
        """
        Closes an active connection to a remote system.

        Args:
            connection (Any): The connection object to be closed.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Optional[Any]: Implementation-specific result or `None`.

        Raises:
            NotImplementedError: If not implemented in a subclass.
        """
        pass

    @abstractmethod
    def exec_cmd(self, command: list[str], connection: Any, *args, **kwargs) -> Tuple[bytes, bytes]:
        """
        Executes a command on a remote system and retrieves its output.

        Args:
            command (list[str]): The command to execute as a list of strings.
            connection (Any): An active connection object to the remote system.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments (e.g., timeout).

        Returns:
            Tuple[bytes, bytes]: A tuple containing:
                - stdout (bytes): The standard output from the command execution.
                - stderr (bytes): The standard error from the command execution.

        Raises:
            NotImplementedError: If not implemented in a subclass.

        Note:
            A `timeout` parameter may be included in `kwargs` to specify the
            maximum duration for command execution.
        """
        # TODO: Add timeout for running a remote command.
        pass
