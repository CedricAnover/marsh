import asyncio
import json

from marsh.core.domain import ProcessSpec, ProcessStatus, Result, Task, Workflow
from marsh.core.observability import (
    Diagnostic,
    DiagnosticCode,
    EventType,
    RuntimeEvent,
    emit_diagnostic,
    emit_event,
)
from marsh.core.runtime import execute_workflow, execute_workflow_async


def test_runtime_event_carries_canonical_correlation_identity():
    event = RuntimeEvent(
        sequence=7,
        event_type=EventType.PROCESS_RUNNING,
        workflow_id="wf",
        execution_id="exec-1",
        task_id="task",
        attempt_id="task:2",
        provider_id="local",
        process_id="proc-1",
        status=ProcessStatus.RUNNING,
    )

    payload = event.to_dict()

    assert payload["execution_id"] == "exec-1"
    assert payload["attempt_id"] == "task:2"
    assert payload["provider_id"] == "local"
    assert payload["process_id"] == "proc-1"
    assert payload["sequence"] == 7
    json.dumps(payload)


def test_redaction_is_recursive_and_preserves_safe_fields():
    event = RuntimeEvent(
        sequence=1,
        event_type=EventType.PROVIDER_SELECTED,
        workflow_id="wf",
        metadata={
            "provider": "local",
            "nested": {"authorization": "Bearer abc123", "safe": "value"},
            "items": [{"api_key": "secret", "status": "running"}],
        },
    )

    safe = event.redacted().to_dict()

    assert safe["metadata"]["provider"] == "local"
    assert safe["metadata"]["nested"]["authorization"] == "[REDACTED]"
    assert safe["metadata"]["nested"]["safe"] == "value"
    assert safe["metadata"]["items"][0]["api_key"] == "[REDACTED]"


def test_diagnostic_has_correlation_and_safe_serialization():
    diagnostic = Diagnostic(
        code=DiagnosticCode.PROVIDER_FAILURE,
        message="provider failed with Authorization: Bearer abc123",
        workflow_id="wf",
        execution_id="exec-1",
        task_id="task",
        attempt_id="task:1",
        provider_id="remote",
        details={"token": "secret", "safe": "value"},
    )

    payload = diagnostic.redacted().to_dict()

    assert payload["code"] == DiagnosticCode.PROVIDER_FAILURE.value
    assert payload["execution_id"] == "exec-1"
    assert "abc123" not in json.dumps(payload)
    assert payload["details"]["token"] == "[REDACTED]"
    assert payload["details"]["safe"] == "value"


def test_observer_only_receives_redacted_event_and_cannot_change_execution():
    seen = []

    class Observer:
        def on_event(self, event):
            seen.append(event)
            raise RuntimeError("observer failure")

    workflow = Workflow(
        id="wf",
        tasks=(
            Task(
                id="task",
                operation=ProcessSpec(
                    executable="python",
                    arguments=("-c", "print('ok')"),
                    environment={"SECRET_TOKEN": "do-not-observe"},
                ),
            ),
        ),
    )

    results = execute_workflow(workflow, observers=(Observer(),))

    assert results["task"].ok
    assert seen
    assert all(event.execution_id == results["task"].execution_id for event in seen if event.task_id == "task")
    assert all("do-not-observe" not in json.dumps(event.to_dict()) for event in seen)


def test_retry_keeps_execution_id_and_changes_attempt_id():
    attempts = []

    def operation(_inputs, _dependencies):
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            return Result(status=ProcessStatus.FAILED, error="transient")
        return Result(status=ProcessStatus.COMPLETED)

    workflow = Workflow(
        id="wf",
        tasks=(Task(id="task", operation=operation, metadata={"idempotent": True}),),
        policy={"retry": {"max_attempts": 2}},
    )
    seen = []

    class Observer:
        def on_event(self, event):
            seen.append(event)

    result = execute_workflow(workflow, observers=(Observer(),))["task"]
    task_events = [event for event in seen if event.task_id == "task"]

    assert result.ok
    assert result.execution_id
    assert result.attempt_id == "task:2"
    assert any(event.event_type is EventType.TASK_RETRY_SCHEDULED for event in task_events)
    assert {event.attempt_id for event in task_events if event.attempt_id} >= {"task:1", "task:2"}
    assert {event.execution_id for event in task_events} == {result.execution_id}


def test_process_and_observation_timeout_are_distinct():
    assert DiagnosticCode.TIMEOUT_PROCESS.value == "TIMEOUT_PROCESS"
    assert DiagnosticCode.TIMEOUT_OBSERVATION.value == "TIMEOUT_OBSERVATION"


def test_cancellation_request_and_confirmation_are_distinct():
    assert EventType.CANCELLATION_REQUESTED.value == "cancellation.requested"
    assert EventType.CANCELLATION_CONFIRMED.value == "cancellation.confirmed"


def test_async_runtime_preserves_execution_correlation():
    async def run():
        seen = []

        class Observer:
            def on_event(self, event):
                seen.append(event)

        workflow = Workflow(
            id="wf",
            tasks=(
                Task(
                    id="task",
                    operation=lambda _inputs, _dependencies: Result(
                        status=ProcessStatus.COMPLETED
                    ),
                ),
            ),
        )
        results = await execute_workflow_async(workflow, observers=(Observer(),))
        return results, seen

    results, seen = asyncio.run(run())
    task_events = [event for event in seen if event.task_id == "task"]
    assert task_events
    assert all(event.execution_id == results["task"].execution_id for event in task_events)


def test_diagnostic_observer_failures_are_isolated():
    seen = []

    class Observer:
        def on_diagnostic(self, diagnostic):
            seen.append(diagnostic)
            raise RuntimeError("observer failure")

    emit_diagnostic(
        Observer(),
        Diagnostic(code=DiagnosticCode.UNKNOWN_STATE, message="state unavailable"),
    )

    assert len(seen) == 1
