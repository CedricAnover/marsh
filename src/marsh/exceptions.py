class CommandError(Exception):
    """Base Class for all Command Errors."""
    pass


class ScriptError(Exception):
    """Base Class for all Script Errors."""
    pass


class DockerError(Exception):
    """Base Class for all Docker Errors."""


class DockerClientError(DockerError):
    pass
