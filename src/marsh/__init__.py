from importlib.metadata import PackageNotFoundError, version

from marsh.core import *

try:
    __version__ = version("marsh-lib")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.4.1"


def __getattr__(name):
    if name == "ssh":
        import importlib

        return importlib.import_module("marsh.ssh")
    raise AttributeError(name)
