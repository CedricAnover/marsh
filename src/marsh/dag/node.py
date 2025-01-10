from typing import Tuple

from ..core import Conveyor
from .startable import Startable


class Node(Startable):
    def __init__(self, name: str, conveyor: Conveyor, **kwargs):
        super().__init__(name)
        self.conveyor = conveyor

        # Conveyor keyword arguments for __call__
        self._kwargs = kwargs

    def start(self) -> Tuple[bytes, bytes]:
        return self.conveyor(**self._kwargs)
