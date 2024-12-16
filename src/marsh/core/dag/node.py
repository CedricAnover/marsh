from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class NodeStateEnum(Enum):
    IDLE = 1
    READY = 2
    RUNNING = 3
    COMPLETE = 4


@dataclass
class Node(ABC):
    label: str
    state: NodeStateEnum = NodeStateEnum.IDLE  # Initial State for all Nodes

    def set_state(self, new_state: NodeStateEnum) -> NodeStateEnum:
        self.state = new_state
        return self.state

    def __eq__(self, other: "Node"):
        return self.label == other.label

    @abstractmethod
    def start(self, dependencies: list[str], *args, **kwargs) -> None:
        pass
