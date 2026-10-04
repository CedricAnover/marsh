"""Conversion between runtime objects and marsh.workflow/v1 data."""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from typing import Any, Mapping

from marsh.core.domain import ProcessSpec, Task, Workflow
from marsh.core.ir.errors import SerializationError, UnsupportedSchemaVersionError
from marsh.core.ir.identifiers import validate_semantic_id
from marsh.core.ir.models import IR_NAME, IR_VERSION, OperationRef, WorkflowDocument
from marsh.core.ir.operations import operation_to_ref, resolve_operation


def _encode(value: Any, path: str = "$") -> Any:
    if isinstance(value, OperationRef):
        return {
            "kind": value.kind,
            "module": value.module,
            "qualname": value.qualname,
        }
    if isinstance(value, ProcessSpec):
        return {
            "kind": "process_spec",
            "executable": value.executable,
            "arguments": [_encode(item, f"{path}.arguments[{i}]") for i, item in enumerate(value.arguments)],
            "environment": _encode(dict(value.environment), f"{path}.environment"),
            "working_directory": value.working_directory,
            "stdin": _encode(value.stdin, f"{path}.stdin") if value.stdin is not None else None,
            "timeout": value.timeout,
            "machine": value.machine,
            "resources": _encode(dict(value.resources), f"{path}.resources"),
            "metadata": _encode(dict(value.metadata), f"{path}.metadata"),
        }
    if callable(value):
        return _encode(operation_to_ref(value), path)
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SerializationError(f"{path}: object keys must be strings")
            result[key] = _encode(item, f"{path}.{key}")
        return {key: result[key] for key in sorted(result)}
    if isinstance(value, (list, tuple)):
        return [_encode(item, f"{path}[{i}]") for i, item in enumerate(value)]
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SerializationError(f"{path}: non-finite numbers are not supported")
        return value
    if isinstance(value, bytes):
        raise SerializationError(f"{path}: bytes are not supported by marsh.workflow/v1")
    raise SerializationError(
        f"{path}: unsupported value type {type(value).__name__}"
    )


def _decode(value: Any, path: str = "$") -> Any:
    if isinstance(value, Mapping):
        if value.get("kind") == "python_callable":
            try:
                reference = OperationRef(
                    kind=value["kind"],
                    module=value["module"],
                    qualname=value["qualname"],
                )
            except (KeyError, ValueError) as exc:
                raise SerializationError(f"{path}: invalid operation reference") from exc
            return resolve_operation(reference)
        if value.get("kind") == "process_spec":
            try:
                return ProcessSpec(
                    executable=value["executable"],
                    arguments=tuple(_decode(item, f"{path}.arguments[{i}]") for i, item in enumerate(value.get("arguments", []))),
                    environment=_decode(value.get("environment", {}), f"{path}.environment"),
                    working_directory=value.get("working_directory"),
                    stdin=_decode(value["stdin"], f"{path}.stdin") if value.get("stdin") is not None else None,
                    timeout=value.get("timeout"),
                    machine=value.get("machine"),
                    resources=_decode(value.get("resources", {}), f"{path}.resources"),
                    metadata=_decode(value.get("metadata", {}), f"{path}.metadata"),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise SerializationError(f"{path}: invalid process specification") from exc
        return {str(key): _decode(item, f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item, f"{path}[{i}]") for i, item in enumerate(value)]
    return value


def document_from_workflow(workflow: Workflow) -> WorkflowDocument:
    """Lower a runtime workflow into the canonical versioned document."""
    validate_semantic_id(workflow.id, "workflow")
    tasks = []
    for task in sorted(workflow.tasks, key=lambda item: item.id):
        validate_semantic_id(task.id, "task")
        tasks.append({
            "id": task.id,
            "operation": _encode(task.operation, f"$.workflow.tasks[{task.id}].operation"),
            "machine": task.machine,
            "inputs": _encode(task.inputs, f"$.workflow.tasks[{task.id}].inputs"),
            "outputs": list(task.outputs),
            "dependencies": sorted(task.dependencies),
            "metadata": _encode(task.metadata, f"$.workflow.tasks[{task.id}].metadata"),
        })
    workflow_data = {
        "id": workflow.id,
        "tasks": tasks,
        "inputs": _encode(workflow.inputs, "$.workflow.inputs"),
        "outputs": _encode(workflow.outputs, "$.workflow.outputs"),
        "metadata": _encode(workflow.metadata, "$.workflow.metadata"),
    }
    return WorkflowDocument(
        schema={"name": IR_NAME, "version": IR_VERSION},
        workflow=workflow_data,
        extensions={},
    )


def document_to_workflow(document: WorkflowDocument) -> Workflow:
    """Reconstruct a runtime Workflow from a canonical document."""
    if document.schema.get("name") != IR_NAME or document.schema.get("version") != IR_VERSION:
        raise UnsupportedSchemaVersionError(
            f"unsupported workflow schema: {document.schema}"
        )
    data = document.workflow
    try:
        workflow = Workflow(
            id=data["id"],
            tasks=tuple(
                Task(
                    id=task["id"],
                    operation=_decode(task["operation"], f"$.workflow.tasks[{task['id']}].operation"),
                    machine=task.get("machine"),
                    inputs=_decode(task.get("inputs", {}), f"$.workflow.tasks[{task['id']}].inputs"),
                    outputs=tuple(task.get("outputs", [])),
                    dependencies=tuple(task.get("dependencies", [])),
                    metadata=_decode(task.get("metadata", {}), f"$.workflow.tasks[{task['id']}].metadata"),
                )
                for task in data["tasks"]
            ),
            inputs=_decode(data.get("inputs", {}), "$.workflow.inputs"),
            outputs=_decode(data.get("outputs", {}), "$.workflow.outputs"),
            metadata=_decode(data.get("metadata", {}), "$.workflow.metadata"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SerializationError("invalid marsh.workflow/v1 document") from exc
    return workflow


def canonical_json(document: WorkflowDocument) -> str:
    """Encode a document with deterministic JSON rules."""
    return json.dumps(
        {"schema": dict(document.schema), "workflow": document.workflow, "extensions": document.extensions},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def document_from_json(value: str) -> WorkflowDocument:
    """Parse and validate a canonical workflow document."""
    try:
        raw = json.loads(value)
        if not isinstance(raw, Mapping):
            raise SerializationError("workflow document must be a JSON object")
        schema = raw.get("schema")
        if not isinstance(schema, Mapping):
            raise SerializationError("workflow document requires schema")
        if schema.get("name") != IR_NAME or schema.get("version") != IR_VERSION:
            raise UnsupportedSchemaVersionError(
                f"unsupported workflow schema: {schema}"
            )
        workflow = raw.get("workflow")
        if not isinstance(workflow, Mapping):
            raise SerializationError("workflow document requires workflow")
        extensions = raw.get("extensions", {})
        if not isinstance(extensions, Mapping):
            raise SerializationError("workflow document extensions must be an object")
        return WorkflowDocument(
            schema=dict(schema),
            workflow=dict(workflow),
            extensions=dict(extensions),
        )
    except json.JSONDecodeError as exc:
        raise SerializationError("invalid workflow JSON") from exc
