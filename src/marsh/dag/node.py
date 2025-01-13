from typing import Tuple

from ..logger import result_logging_decorator
from ..core import Conveyor
from .startable import Startable


class Node(Startable):
    """
    A Node represents an object that can be started, typically as part of a workflow or graph.

    This class extends `Startable` and represents a node in a directed acyclic graph (DAG) or similar structure.
    Each node is responsible for starting a process using a `Conveyor` object. The `start` method invokes the `Conveyor`
    with the provided keyword arguments, returning the result as a 2-tuple of bytes.

    Attributes:
        name (str): The name of the node, inherited from the `Startable` base class.
        conveyor (Conveyor): The `Conveyor` object responsible for carrying out the node's operation.
        _kwargs (dict): A dictionary of keyword arguments used when calling the `Conveyor`.

    Methods:
        start() -> Tuple[bytes, bytes]:
            Executes the `Conveyor` with the provided arguments, returning the result as a tuple of bytes.
    """

    def __init__(self, name: str, conveyor: Conveyor, **kwargs):
        """
        Initializes a Node object with a name and a Conveyor.

        Args:
            name (str): The name of the node.
            conveyor (Conveyor): The `Conveyor` object that will perform the operation associated with this node.
            **kwargs: Additional keyword arguments to be passed to the `Conveyor` when called.
        """
        super().__init__(name)
        self.conveyor = conveyor

        # Conveyor keyword arguments for __call__
        self._kwargs = kwargs

    @result_logging_decorator(__name__)
    def start(self) -> Tuple[bytes, bytes]:
        """
        Starts the operation associated with the Node by invoking the Conveyor.

        This method calls the `Conveyor` object with the stored keyword arguments and returns a tuple of bytes
        representing the result of the operation.

        Returns:
            Tuple[bytes, bytes]: A tuple containing two byte sequences as the result of the Conveyor operation.
        """
        return self.conveyor(**self._kwargs)
