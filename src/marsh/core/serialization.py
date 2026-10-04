"""Public compatibility façade for marsh.workflow/v1 serialization."""

from __future__ import annotations

from typing import Any, Mapping

from marsh.core.configuration import normalize_workflow
from marsh.core.domain import Workflow
from marsh.core.ir.codecs import (
    canonical_json,
    document_from_json,
    document_from_workflow,
    document_to_workflow,
)
from marsh.core.ir.models import WorkflowDocument
from marsh.core.runtime import plan_workflow


def validate_workflow(workflow: Workflow | Mapping[str, Any]) -> tuple[str, ...]:
    """Validate dependencies using the canonical planning semantic owner."""
    return plan_workflow(normalize_workflow(workflow)).order


def workflow_to_document(workflow: Workflow | Mapping[str, Any]) -> WorkflowDocument:
    """Lower a workflow to the versioned canonical IR document."""
    return document_from_workflow(normalize_workflow(workflow))


def workflow_to_dict(workflow: Workflow | Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical v1 document as plain Python data."""
    document = workflow_to_document(workflow)
    return {
        "schema": dict(document.schema),
        "workflow": document.workflow,
        "extensions": dict(document.extensions),
    }


def workflow_to_json(workflow: Workflow | Mapping[str, Any]) -> str:
    """Return deterministic marsh.workflow/v1 JSON."""
    return canonical_json(workflow_to_document(workflow))


def workflow_from_dict(value: Mapping[str, Any]) -> Workflow:
    """Reconstruct a runtime workflow from a canonical v1 document."""
    if "schema" not in value:
        raise ValueError("workflow document requires schema")
    document = WorkflowDocument(
        schema=dict(value["schema"]),
        workflow=dict(value["workflow"]),
        extensions=dict(value.get("extensions", {})),
    )
    return document_to_workflow(document)


def workflow_from_json(value: str) -> Workflow:
    """Reconstruct a runtime workflow from canonical v1 JSON."""
    return document_to_workflow(document_from_json(value))


__all__ = [
    "canonical_json",
    "validate_workflow",
    "workflow_to_document",
    "workflow_to_dict",
    "workflow_to_json",
    "workflow_from_dict",
    "workflow_from_json",
]
