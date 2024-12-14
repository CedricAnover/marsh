from abc import ABC, abstractmethod


class Connector(ABC):
    @abstractmethod
    def connect(self, *conn_args, **conn_kwargs):
        pass

    @abstractmethod
    def disconnect(self, *args, **kwargs):
        pass
