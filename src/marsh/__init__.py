from marsh.core import *


def __getattr__(name):
    if name == "ssh":
        import importlib

        return importlib.import_module("marsh.ssh")
    raise AttributeError(name)
