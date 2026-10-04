"""Workflow validation and deterministic serialization."""

import json
from typing import Any, Mapping

from marsh.core.configuration import normalize_workflow
from marsh.core.domain import Workflow
from marsh.core.runtime import plan_workflow


def validate_workflow(workflow: Workflow | Mapping[str, Any]) -> tuple[str, ...]:
    """Validate dependencies using the canonical planning semantic owner."""

    return plan_workflow(normalize_workflow(workflow)).order


def _data(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _data(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, tuple):
        return [_data(item) for item in value]
    if isinstance(value, list):
        return [_data(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"workflow contains a non-serializable value: {type(value).__name__}")


def workflow_to_dict(workflow: Workflow | Mapping[str, Any]) -> dict[str, Any]:
    workflow = normalize_workflow(workflow)
    validate_workflow(workflow)
    return _data({
        "id": workflow.id,
        "tasks": [
            {
                "id": task.id,
                "operation": task.operation,
                "machine": task.machine,
                "inputs": task.inputs,
                "outputs": task.outputs,
                "dependencies": task.dependencies,
                "metadata": task.metadata,
            }
            for task in sorted(workflow.tasks, key=lambda item: item.id)
        ],
        "inputs": workflow.inputs,
        "outputs": workflow.outputs,
        "metadata": workflow.metadata,
    })


def workflow_to_json(workflow: Workflow | Mapping[str, Any]) -> str:
    return json.dumps(workflow_to_dict(workflow), sort_keys=True, separators=(",", ":"))


def workflow_from_dict(value: Mapping[str, Any]) -> Workflow:
    workflow = normalize_workflow(value)
    validate_workflow(workflow)
    return workflow


def workflow_from_json(value: str) -> Workflow:
    return workflow_from_dict(json.loads(value))
