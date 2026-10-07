"""Canonical runtime events, diagnostics, and secret-safe observer boundaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol

from marsh.core.domain import ProcessStatus
from marsh.diagnostics import redact


class EventType(str, Enum):
    """Stable vocabulary for canonical runtime observations."""

    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_SKIPPED = "task.skipped"
    TASK_RETRY_SCHEDULED = "task.retry_scheduled"
    TASK_CANCELLED = "task.cancelled"
    TASK_TIMED_OUT = "task.timed_out"
    PROVIDER_SELECTED = "provider.selected"
    PROVIDER_CAPABILITY_CHECKED = "provider.capability_checked"
    PROVIDER_REJECTED = "provider.rejected"
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    ATTEMPT_STARTED = "attempt.started"
    ATTEMPT_COMPLETED = "attempt.completed"
    PROCESS_CREATED = "process.created"
    PROCESS_STARTED = "process.started"
    PROCESS_RUNNING = "process.running"
    PROCESS_STOPPING = "process.stopping"
    PROCESS_COMPLETED = "process.completed"
    PROCESS_FAILED = "process.failed"
    PROCESS_CANCELLED = "process.cancelled"
    PROCESS_TIMED_OUT = "process.timed_out"
    PROCESS_UNKNOWN = "process.unknown"
    PROCESS_AMBIGUOUS = "process.ambiguous"
    RESULT_MATERIALIZED = "result.materialized"
    ARTIFACT_MATERIALIZED = "artifact.materialized"
    ARTIFACT_VERIFICATION_FAILED = "artifact.verification_failed"
    OBSERVATION_MISSING = "observation.missing"
    OBSERVATION_DUPLICATE = "observation.duplicate"
    OBSERVATION_LATE = "observation.late"
    OBSERVATION_CONFLICTING = "observation.conflicting"
    CANCELLATION_REQUESTED = "cancellation.requested"
    CANCELLATION_CONFIRMED = "cancellation.confirmed"


class DiagnosticCode(str, Enum):
    """Stable operational diagnostic categories."""

    TIMEOUT_PROCESS = "TIMEOUT_PROCESS"
    TIMEOUT_OBSERVATION = "TIMEOUT_OBSERVATION"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    CANCELLATION_CONFIRMED = "CANCELLATION_CONFIRMED"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    CLEANUP_FAILURE = "CLEANUP_FAILURE"
    OBSERVATION_FAILURE = "OBSERVATION_FAILURE"
    UNKNOWN_STATE = "UNKNOWN_STATE"
    AMBIGUOUS_STATE = "AMBIGUOUS_STATE"
    REDACTION_APPLIED = "REDACTION_APPLIED"
    ARTIFACT_VERIFICATION_FAILURE = "ARTIFACT_VERIFICATION_FAILURE"


def _safe(value: Any) -> Any:
    """Convert dataclass/enum values into JSON-safe diagnostic data."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _safe(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class RuntimeEvent:
    """Correlated, serializable evidence projected from canonical runtime state."""

    sequence: int
    event_type: EventType
    workflow_id: str
    task_id: str | None = None
    execution_id: str | None = None
    attempt_id: str | None = None
    provider_id: str | None = None
    process_id: str | None = None
    status: ProcessStatus | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def redacted(self) -> "RuntimeEvent":
        """Return an observer-safe copy with recursive secret redaction."""
        return RuntimeEvent(
            sequence=self.sequence,
            event_type=self.event_type,
            workflow_id=self.workflow_id,
            task_id=self.task_id,
            execution_id=self.execution_id,
            attempt_id=self.attempt_id,
            provider_id=self.provider_id,
            process_id=self.process_id,
            status=self.status,
            timestamp=self.timestamp,
            result=redact(_safe(self.result)),
            metadata=redact(_safe(self.metadata)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event without exposing implementation-specific objects."""
        return {
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "attempt_id": self.attempt_id,
            "provider_id": self.provider_id,
            "process_id": self.process_id,
            "status": self.status.value if self.status is not None else None,
            "timestamp": self.timestamp,
            "result": _safe(self.result),
            "metadata": _safe(self.metadata),
        }


@dataclass(frozen=True)
class Diagnostic:
    """Correlated operational evidence that never defines execution outcome."""

    code: DiagnosticCode
    message: str
    severity: str = "info"
    workflow_id: str | None = None
    execution_id: str | None = None
    task_id: str | None = None
    attempt_id: str | None = None
    provider_id: str | None = None
    process_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in {"info", "warning", "error"}:
            raise ValueError("severity must be info, warning, or error")

    def redacted(self) -> "Diagnostic":
        """Return an observer-safe diagnostic with recursive secret redaction."""
        safe_message = redact(self.message)
        return Diagnostic(
            code=self.code,
            message=safe_message,
            severity=self.severity,
            workflow_id=self.workflow_id,
            execution_id=self.execution_id,
            task_id=self.task_id,
            attempt_id=self.attempt_id,
            provider_id=self.provider_id,
            process_id=self.process_id,
            details=redact(_safe(self.details)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the diagnostic for human or machine-readable observers."""
        return {
            "code": self.code.value,
            "severity": self.severity,
            "message": self.message,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "provider_id": self.provider_id,
            "process_id": self.process_id,
            "details": _safe(self.details),
        }


class Observer(Protocol):
    """Read-only observer boundary for runtime evidence."""

    def on_event(self, event: RuntimeEvent) -> None:
        ...


class DiagnosticObserver(Protocol):
    """Read-only observer boundary for operational diagnostics."""

    def on_diagnostic(self, diagnostic: Diagnostic) -> None:
        ...


class OpenTelemetryObserver:
    """Optional OpenTelemetry API adapter; exporters remain application-owned."""

    def __init__(self, tracer_name: str = "marsh") -> None:
        try:
            from opentelemetry import trace
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "OpenTelemetry support requires the optional opentelemetry-api package"
            ) from exc
        self._tracer = trace.get_tracer(tracer_name)

    def on_event(self, event: RuntimeEvent) -> None:
        """Project one canonical event into an application-owned trace span."""
        with self._tracer.start_as_current_span(f"marsh.{event.event_type.value}") as span:
            for key, value in event.to_dict().items():
                if value is None or key in {"result", "metadata"}:
                    continue
                span.set_attribute(f"marsh.{key}", str(value))
            span.add_event(event.event_type.value, attributes={
                "marsh.sequence": event.sequence,
                "marsh.workflow_id": event.workflow_id,
            })


def emit_event(observer: Observer, event: RuntimeEvent) -> None:
    """Deliver a redacted event while isolating observer failures."""
    try:
        observer.on_event(event.redacted())
    except Exception:
        # Observers are downstream projections and must never affect execution.
        return


def emit_diagnostic(observer: DiagnosticObserver, diagnostic: Diagnostic) -> None:
    """Deliver a redacted diagnostic while isolating observer failures."""
    try:
        observer.on_diagnostic(diagnostic.redacted())
    except Exception:
        # Diagnostics are evidence, not control flow.
        return
