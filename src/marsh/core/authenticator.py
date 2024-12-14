from abc import ABC, abstractmethod


class Authenticator(ABC):
    @abstractmethod
    def authenticate(self, *args, **kwargs):
        pass
