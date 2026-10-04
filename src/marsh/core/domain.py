"""Stable domain contracts for Marsh's workflow and execution kernel.

This module is intentionally dependency-free. It defines semantics and narrow
capabilities; concrete execution mechanisms remain in existing adapters/providers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


class ProcessStatus(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"


_TERMINAL_STATUSES = frozenset(
    {
        ProcessStatus.COMPLETED,
        ProcessStatus.FAILED,
        ProcessStatus.CANCELLED,
        ProcessStatus.TIMED_OUT,
        ProcessStatus.SKIPPED,
    }
)

_ALLOWED_TRANSITIONS = {
    ProcessStatus.CREATED: frozenset({ProcessStatus.STARTING, ProcessStatus.CANCELLED}),
    ProcessStatus.STARTING: frozenset(
        {ProcessStatus.RUNNING, ProcessStatus.FAILED, ProcessStatus.CANCELLED}
    ),
    ProcessStatus.RUNNING: frozenset(
        {
            ProcessStatus.STOPPING,
            ProcessStatus.COMPLETED,
            ProcessStatus.FAILED,
            ProcessStatus.CANCELLED,
            ProcessStatus.TIMED_OUT,
        }
    ),
    ProcessStatus.STOPPING: frozenset(
        {ProcessStatus.COMPLETED, ProcessStatus.FAILED, ProcessStatus.CANCELLED}
    ),
}


def can_transition(current: ProcessStatus, target: ProcessStatus) -> bool:
    """Return whether a lifecycle transition is explicitly supported."""

    if current in _TERMINAL_STATUSES:
        return False
    return target in _ALLOWED_TRANSITIONS.get(current, frozenset())


def is_terminal(status: ProcessStatus) -> bool:
    """Return whether a process status represents a terminal outcome."""

    return status in _TERMINAL_STATUSES


@dataclass(frozen=True)
class ProcessSpec:
    """Reified description of one process before execution."""

    executable: str
    arguments: tuple[str, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict)
    working_directory: str | None = None
    stdin: bytes | None = None
    timeout: float | None = None
    machine: str | None = None
    resources: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.executable or not self.executable.strip():
            raise ValueError("executable must be non-empty")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        object.__setattr__(self, "arguments", tuple(self.arguments))


@dataclass(frozen=True)
class Result:
    """Structured outcome of a process execution."""

    stdout: bytes = b""
    stderr: bytes = b""
    exit_code: int | None = None
    status: ProcessStatus = ProcessStatus.COMPLETED
    error: str | None = None
    duration: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == ProcessStatus.COMPLETED and self.error is None

    @property
    def failed(self) -> bool:
        return self.status in {
            ProcessStatus.FAILED,
            ProcessStatus.TIMED_OUT,
        } or self.error is not None


@dataclass(frozen=True)
class Task:
    """A unit of work and its control dependencies."""

    id: str
    operation: Any
    machine: str | None = None
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("task id must be non-empty")
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        if self.id in self.dependencies:
            raise ValueError(f"task {self.id!r} cannot depend on itself")


@dataclass(frozen=True)
class Workflow:
    """A reified collection of tasks and their relationships."""

    id: str
    tasks: tuple[Task, ...] = ()
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("workflow id must be non-empty")
        object.__setattr__(self, "tasks", tuple(self.tasks))
        task_ids = [task.id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("workflow contains duplicate task ids")
        known_ids = set(task_ids)
        for task in self.tasks:
            unknown = set(task.dependencies) - known_ids
            if unknown:
                names = ", ".join(sorted(unknown))
                raise ValueError(f"task {task.id!r} has unknown dependencies: {names}")

    def task(self, task_id: str) -> Task:
        """Return a task by id, or raise KeyError when it is absent."""

        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(task_id)


@runtime_checkable
class Startable(Protocol):
    """Capability for processes that can be started."""

    def start(self) -> Any:
        ...


@runtime_checkable
class Waitable(Protocol):
    """Capability for processes whose terminal result can be awaited."""

    def wait(self) -> Result:
        ...


@runtime_checkable
class Pollable(Protocol):
    """Capability for processes whose current status can be queried."""

    def poll(self) -> ProcessStatus:
        ...


@runtime_checkable
class Stoppable(Protocol):
    """Capability for processes that support graceful stopping."""

    def stop(self) -> Any:
        ...


@runtime_checkable
class Terminable(Protocol):
    """Capability for processes that support forced termination."""

    def terminate(self) -> Any:
        ...


@runtime_checkable
class Killable(Protocol):
    """Capability for processes that support immediate termination."""

    def kill(self) -> Any:
        ...


@runtime_checkable
class Resultable(Protocol):
    """Capability for processes that expose a structured result."""

    def result(self) -> Result:
        ...


@runtime_checkable
class Process(Protocol):
    """Minimal process contract: start and wait are the portable core."""

    def start(self) -> Any:
        ...

    def wait(self) -> Result:
        ...


@runtime_checkable
class Machine(Protocol):
    """Execution environment capable of materializing a process."""

    def create_process(self, spec: ProcessSpec) -> Process:
        ...


@runtime_checkable
class Scheduler(Protocol):
    """Determines execution order without owning process semantics."""

    def schedule(self, workflow: Workflow) -> Sequence[Task]:
        ...
