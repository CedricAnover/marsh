from abc import ABC, abstractmethod
from typing import Optional, Any


class Startable(ABC):
    def __init__(self, name: str):
        self.name = name  # Hashable name for Node and Dag

    @abstractmethod
    def start(self, *args, **kwargs) -> Optional[Any]:
        pass
