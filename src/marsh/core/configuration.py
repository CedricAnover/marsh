"""Boundary configuration models for the canonical Marsh workflow IR."""

from __future__ import annotations

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
        raise ValueError(f"{field_name} must be non-empty")
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
class MachineConfig:
    """Provider-neutral machine configuration."""

    name: str
    provider: str = "local"
    options: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MachineConfig":
        if not isinstance(value, Mapping):
            raise ValueError("machine configuration must be a mapping")
        return cls(
            name=_identifier(value.get("name"), "machine name"),
            provider=_identifier(value.get("provider", "local"), "machine provider"),
            options=_mapping(value.get("options"), "machine options"),
        )


@dataclass(frozen=True)
class SchedulerConfig:
    """Provider-independent scheduler selection and concurrency configuration."""

    strategy: str = "sequential"
    max_concurrency: int = 1

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "SchedulerConfig":
        value = value or {}
        if not isinstance(value, Mapping):
            raise ValueError("scheduler configuration must be a mapping")
        strategy = _identifier(value.get("strategy", "sequential"), "scheduler strategy")
        max_concurrency = value.get("max_concurrency", 1)
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool) or max_concurrency < 1:
            raise ValueError("scheduler max_concurrency must be a positive integer")
        return cls(strategy=strategy, max_concurrency=max_concurrency)


@dataclass(frozen=True)
class PolicyConfig:
    """Opaque, validated policy data kept independent of runtime policy classes."""

    values: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "PolicyConfig":
        return cls(values=_mapping(value, "policy configuration"))


@dataclass(frozen=True)
class ProviderConfig:
    """Provider-neutral provider selection at the configuration boundary."""

    name: str
    options: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProviderConfig":
        if not isinstance(value, Mapping):
            raise ValueError("provider configuration must be a mapping")
        return cls(
            name=_identifier(value.get("name"), "provider name"),
            options=_mapping(value.get("options"), "provider options"),
        )


@dataclass(frozen=True)
class WorkflowConfig:
    """Validated, syntax-neutral configuration for a workflow."""

    id: str
    tasks: tuple[TaskConfig, ...] = ()
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    machines: tuple[MachineConfig, ...] = ()
    providers: tuple[ProviderConfig, ...] = ()
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WorkflowConfig":
        if not isinstance(value, Mapping):
            raise ValueError("workflow must be a mapping")
        allowed = {
            "id", "tasks", "inputs", "outputs", "metadata",
            "machines", "providers", "scheduler", "policy",
        }
        unknown = set(value) - allowed
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"workflow has unknown fields: {names}")
        if "id" not in value:
            raise ValueError("workflow id is required")
        workflow_id = _identifier(value["id"], "workflow id")
        tasks = tuple(
            TaskConfig.from_mapping(task)
            for task in _sequence(value.get("tasks"), "workflow tasks")
        )
        machines = tuple(
            MachineConfig.from_mapping(item)
            for item in _sequence(value.get("machines"), "workflow machines")
        )
        providers = tuple(
            ProviderConfig.from_mapping(item)
            for item in _sequence(value.get("providers"), "workflow providers")
        )
        return cls(
            id=workflow_id,
            tasks=tasks,
            inputs=_mapping(value.get("inputs"), "workflow inputs"),
            outputs=_mapping(value.get("outputs"), "workflow outputs"),
            metadata=_mapping(value.get("metadata"), "workflow metadata"),
            machines=machines,
            providers=providers,
            scheduler=SchedulerConfig.from_mapping(value.get("scheduler")),
            policy=PolicyConfig.from_mapping(value.get("policy")),
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
    """Normalize Python or mapping authoring into the runtime Workflow contract."""
    if isinstance(value, Workflow):
        return value
    if isinstance(value, WorkflowConfig):
        return value.to_workflow()
    return WorkflowConfig.from_mapping(value).to_workflow()
