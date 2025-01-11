from abc import ABC, abstractmethod
from typing import Optional, Any


class Startable(ABC):
    """
    Abstract base class for objects that can be started, such as nodes or DAGs.

    This class defines a common interface for objects that need to be started.
    Subclasses like `Node` and `Dag` will implement the `start` method with their own logic,
    while inheriting from `Startable` to ensure they follow the expected contract for starting.

    Attributes:
        name (str): A hashable name that identifies the object within a node or directed acyclic graph (DAG).
            This will be used to define the graph in `graphlib.TopologicalSorter`.

    Methods:
        start(*args, **kwargs):
            Starts the object with optional arguments. Subclasses must implement this method with their own logic,
            defining how the object is started. It may return any type or `None`.
    """

    def __init__(self, name: str):
        """
        Initializes a Startable object with a given name.

        Args:
            name (str): A hashable name for the node or DAG.
                This name is used to identify and reference the object.
        """
        self.name = name  # Hashable name for Node and Dag

    @abstractmethod
    def start(self, *args, **kwargs) -> Optional[Any]:
        """
        Abstract method that starts the object.

        This method must be implemented by subclasses such as `Node` or `Dag` to define the specific behavior
        for starting the object. It should handle the logic for initiating the object's state or execution.

        Args:
            *args: Positional arguments passed to the method.
            **kwargs: Keyword arguments passed to the method.

        Returns:
            Optional[Any]: The result of the start operation, which may be of any type, or `None`.
        """
        pass
