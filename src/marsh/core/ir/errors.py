"""Errors raised at the canonical Workflow IR boundary."""


class SerializationError(ValueError):
    """Base error for invalid canonical workflow serialization."""


class UnsupportedSchemaVersionError(SerializationError):
    """Raised when a workflow document uses an unknown IR version."""


class OperationResolutionError(SerializationError):
    """Raised when an executable operation cannot be reconstructed."""
