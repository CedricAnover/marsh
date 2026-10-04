"""Canonical Workflow IR for Marsh."""

from marsh.core.ir.errors import (
    OperationResolutionError,
    SerializationError,
    UnsupportedSchemaVersionError,
)
from marsh.core.ir.models import (
    IR_VERSION,
    OperationRef,
    WorkflowDocument,
    WorkflowIR,
)
from marsh.core.ir.operations import resolve_operation
from marsh.core.ir.codecs import (
    canonical_json,
    document_from_workflow,
    document_to_workflow,
)

__all__ = [
    "IR_VERSION",
    "OperationRef",
    "WorkflowDocument",
    "WorkflowIR",
    "OperationResolutionError",
    "SerializationError",
    "UnsupportedSchemaVersionError",
    "canonical_json",
    "document_from_workflow",
    "document_to_workflow",
    "resolve_operation",
]
