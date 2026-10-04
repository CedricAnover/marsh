"""Stable runtime lifecycle events and observer boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol

from marsh.core.domain import ProcessStatus


class EventType(str, Enum):
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_SKIPPED = "task.skipped"
    TASK_RETRY_SCHEDULED = "task.retry_scheduled"
    TASK_CANCELLED = "task.cancelled"
    TASK_TIMED_OUT = "task.timed_out"


@dataclass(frozen=True)
class RuntimeEvent:
    sequence: int
    event_type: EventType
    workflow_id: str
    task_id: str | None = None
    status: ProcessStatus | None = None
    result: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def redacted(self) -> "RuntimeEvent":
        return RuntimeEvent(
            sequence=self.sequence,
            event_type=self.event_type,
            workflow_id=self.workflow_id,
            task_id=self.task_id,
            status=self.status,
            result=self.result,
            metadata={
                key: "[REDACTED]" if _is_sensitive_key(key) else value
                for key, value in self.metadata.items()
            },
        )


class Observer(Protocol):
    def on_event(self, event: RuntimeEvent) -> None:
        ...


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(
        marker in normalized
        for marker in ("password", "passwd", "secret", "token", "api_key", "apikey", "private_key")
    )


def emit_event(observer: Observer, event: RuntimeEvent) -> None:
    try:
        observer.on_event(event.redacted())
    except Exception:
        # Observers are observational only and must never affect execution.
        return
