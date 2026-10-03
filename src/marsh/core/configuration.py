"""Boundary configuration models for the canonical Marsh workflow IR.

Configuration objects validate and normalize authoring data before runtime
objects are materialized. They intentionally remain separate from runtime
domain objects.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from marsh.core.domain import Task, Workflow


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return dict(value)


def _sequence(value: Any, field_name: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list or tuple")
    return tuple(value)


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class TaskConfig:
    """Validated, syntax-neutral configuration for one task."""

    id: str
    operation: Any
    machine: str | None = None
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TaskConfig":
        if not isinstance(value, Mapping):
            raise ValueError("task must be a mapping")

        allowed = {
            "id", "operation", "machine", "inputs", "outputs",
            "dependencies", "metadata",
        }
        unknown = set(value) - allowed
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"task has unknown fields: {names}")

        if "id" not in value:
            raise ValueError("task id is required")
        task_id = _identifier(value["id"], "task id")
        if "operation" not in value:
            raise ValueError(f"task {task_id!r} operation is required")

        outputs = _sequence(value.get("outputs"), "task outputs")
        dependencies = _sequence(value.get("dependencies"), "task dependencies")
        if not all(isinstance(item, str) and item.strip() for item in outputs):
            raise ValueError("task outputs must contain non-empty strings")
        if not all(isinstance(item, str) and item.strip() for item in dependencies):
            raise ValueError("task dependencies must contain non-empty strings")

        return cls(
            id=task_id,
            operation=value["operation"],
            machine=value.get("machine"),
            inputs=_mapping(value.get("inputs"), "task inputs"),
            outputs=tuple(outputs),
            dependencies=tuple(dependencies),
            metadata=_mapping(value.get("metadata"), "task metadata"),
        )

    def to_workflow_task(self) -> Task:
        return Task(
            id=self.id,
            operation=self.operation,
            machine=self.machine,
            inputs=self.inputs,
            outputs=self.outputs,
            dependencies=self.dependencies,
            metadata=self.metadata,
        )


@dataclass(frozen=True)
class WorkflowConfig:
    """Validated, syntax-neutral configuration for a workflow."""

    id: str
    tasks: tuple[TaskConfig, ...] = ()
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WorkflowConfig":
        if not isinstance(value, Mapping):
            raise ValueError("workflow must be a mapping")

        allowed = {"id", "tasks", "inputs", "outputs", "metadata"}
        unknown = set(value) - allowed
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"workflow has unknown fields: {names}")
        if "id" not in value:
            raise ValueError("workflow id is required")
        workflow_id = _identifier(value["id"], "workflow id")

        raw_tasks = _sequence(value.get("tasks"), "workflow tasks")
        tasks = tuple(TaskConfig.from_mapping(task) for task in raw_tasks)

        return cls(
            id=workflow_id,
            tasks=tasks,
            inputs=_mapping(value.get("inputs"), "workflow inputs"),
            outputs=_mapping(value.get("outputs"), "workflow outputs"),
            metadata=_mapping(value.get("metadata"), "workflow metadata"),
        )

    def to_workflow(self) -> Workflow:
        return Workflow(
            id=self.id,
            tasks=tuple(task.to_workflow_task() for task in self.tasks),
            inputs=self.inputs,
            outputs=self.outputs,
            metadata=self.metadata,
        )


def normalize_workflow(value: Workflow | WorkflowConfig | Mapping[str, Any]) -> Workflow:
    """Normalize Python or mapping authoring into the canonical Workflow IR."""

    if isinstance(value, Workflow):
        return value
    if isinstance(value, WorkflowConfig):
        return value.to_workflow()
    return WorkflowConfig.from_mapping(value).to_workflow()
