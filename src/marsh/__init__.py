from importlib.metadata import PackageNotFoundError, version\n\nfrom marsh.core import *\n\ntry:\n    __version__ = version("marsh-lib")\nexcept PackageNotFoundError:  # pragma: no cover\n    __version__ = "0.3.9"


def __getattr__(name):
    if name == "ssh":
        import importlib

        return importlib.import_module("marsh.ssh")
    raise AttributeError(name)
