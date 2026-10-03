"""Workflow validation and deterministic serialization."""

import json
from heapq import heappop, heappush
from typing import Any, Mapping

from marsh.core.configuration import normalize_workflow
from marsh.core.domain import Workflow


def validate_workflow(workflow: Workflow | Mapping[str, Any]) -> tuple[str, ...]:
    workflow = normalize_workflow(workflow)
    tasks = {task.id: task for task in workflow.tasks}
    indegree = {task_id: 0 for task_id in tasks}
    dependents = {task_id: [] for task_id in tasks}
    for task in workflow.tasks:
        for dependency in task.dependencies:
            if dependency not in tasks:
                raise ValueError(f"task {task.id!r} has unknown dependencies: {dependency}")
            indegree[task.id] += 1
            dependents[dependency].append(task.id)
    ready = []
    for task_id, degree in indegree.items():
        if degree == 0:
            heappush(ready, task_id)
    order = []
    while ready:
        task_id = heappop(ready)
        order.append(task_id)
        for dependent in sorted(dependents[task_id]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heappush(ready, dependent)
    if len(order) != len(tasks):
        raise ValueError("workflow contains a dependency cycle")
    return tuple(order)


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
