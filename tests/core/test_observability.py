import pytest

from marsh.core.domain import ProcessStatus, Result, Task, Workflow
from marsh.core.observability import EventType, RuntimeEvent, emit_event


def test_runtime_event_has_stable_sequence_and_identity():
    event = RuntimeEvent(
        sequence=1,
        event_type=EventType.TASK_COMPLETED,
        workflow_id="wf",
        task_id="task",
        status=ProcessStatus.COMPLETED,
    )

    assert event.sequence == 1
    assert event.event_type is EventType.TASK_COMPLETED
    assert event.workflow_id == "wf"
    assert event.task_id == "task"
    assert event.status is ProcessStatus.COMPLETED


def test_observer_errors_cannot_corrupt_execution():
    seen = []

    class FailingObserver:
        def on_event(self, event):
            seen.append(event)
            raise RuntimeError("observer failure")

    event = RuntimeEvent(
        sequence=1,
        event_type=EventType.WORKFLOW_STARTED,
        workflow_id="wf",
    )

    emit_event(FailingObserver(), event)

    assert seen == [event]


def test_sensitive_metadata_is_redacted_by_default():
    event = RuntimeEvent(
        sequence=1,
        event_type=EventType.TASK_STARTED,
        workflow_id="wf",
        metadata={"token": "secret", "normal": "value"},
    )

    safe = event.redacted()

    assert safe.metadata["token"] == "[REDACTED]"
    assert safe.metadata["normal"] == "value"
