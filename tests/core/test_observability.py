import asyncio
import json
import sys

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


def test_runtime_event_redaction_covers_result_payload_and_authorization_forms():
    event = RuntimeEvent(
        sequence=2,
        event_type=EventType.RESULT_MATERIALIZED,
        workflow_id="wf",
        result={
            "stdout": "Authorization: Bearer top-secret",
            "payload": {"password": "pw", "safe": "ok"},
            "items": [{"private_key": "private-key-secret", "value": "ok"}],
        },
    )

    payload = event.redacted().to_dict()

    encoded = json.dumps(payload)
    assert "top-secret" not in encoded
    assert "pw" not in encoded
    assert "private-key-secret" not in encoded
    assert payload["result"]["payload"]["safe"] == "ok"


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


def test_diagnostic_rejects_unknown_severity():
    try:
        Diagnostic(code=DiagnosticCode.UNKNOWN_STATE, message="x", severity="debug")
    except ValueError as exc:
        assert "severity" in str(exc)
    else:
        raise AssertionError("invalid diagnostic severity must be rejected")


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
                    executable=sys.executable,
                    arguments=("-c", "print('ok')"),
                    environment={"SECRET_TOKEN": "do-not-observe"},
                ),
            ),
        ),
    )

    results = execute_workflow(workflow, observers=(Observer(),))

    assert results["task"].ok
    assert seen
    assert all(
        event.execution_id == results["task"].execution_id
        for event in seen
        if event.task_id == "task"
    )
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
    assert {event.attempt_id for event in task_events if event.attempt_id} >= {
        "task:1",
        "task:2",
    }
    assert {event.execution_id for event in task_events} == {result.execution_id}


def test_execution_id_is_stable_for_equivalent_workflow_invocations():
    workflow = Workflow(
        id="stable",
        tasks=(
            Task(
                id="task",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "print('stable')"),
                ),
            ),
        ),
    )
    seen = []

    class Observer:
        def on_event(self, event):
            if event.task_id == "task" and event.execution_id:
                seen.append(event.execution_id)

    execute_workflow(workflow, observers=(Observer(),))
    execute_workflow(workflow, observers=(Observer(),))

    assert len(seen) >= 2
    assert len(set(seen)) == 1


def test_callable_exception_is_classified_and_does_not_leak_secret():
    seen = []
    diagnostics = []

    class Observer:
        def on_event(self, event):
            seen.append(event)

        def on_diagnostic(self, diagnostic):
            diagnostics.append(diagnostic)

    def operation(_inputs, _dependencies):
        raise RuntimeError("Authorization: Bearer super-secret")

    workflow = Workflow(
        id="exception",
        tasks=(Task(id="task", operation=operation),),
    )

    result = execute_workflow(workflow, observers=(Observer(),))["task"]

    assert result.failed
    assert diagnostics
    assert diagnostics[0].code is DiagnosticCode.PROVIDER_FAILURE
    assert "super-secret" not in json.dumps(diagnostics[0].to_dict())
    assert any(event.event_type is EventType.OBSERVATION_CONFLICTING for event in seen)


def test_dependency_skip_is_correlated_and_observable():
    seen = []

    class Observer:
        def on_event(self, event):
            seen.append(event)

    workflow = Workflow(
        id="skip",
        tasks=(
            Task(
                id="dependent",
                operation=lambda *_: Result(status=ProcessStatus.COMPLETED),
                dependencies=("failed",),
            ),
            Task(
                id="failed",
                operation=lambda *_: Result(
                    status=ProcessStatus.FAILED, error="boom"
                ),
            ),
        ),
    )

    results = execute_workflow(workflow, observers=(Observer(),))

    skipped = [event for event in seen if event.event_type is EventType.TASK_SKIPPED]
    assert skipped
    assert skipped[0].task_id == "dependent"
    assert skipped[0].execution_id == results["failed"].execution_id
    assert results["dependent"].status is ProcessStatus.SKIPPED


def test_process_failure_emits_terminal_process_and_task_failure_events():
    seen = []

    class Observer:
        def on_event(self, event):
            seen.append(event)

    workflow = Workflow(
        id="process-failure",
        tasks=(
            Task(
                id="task",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "raise SystemExit(7)"),
                ),
            ),
        ),
    )

    results = execute_workflow(workflow, observers=(Observer(),))

    assert results["task"].status is ProcessStatus.FAILED
    assert any(event.event_type is EventType.PROCESS_FAILED for event in seen)
    assert any(event.event_type is EventType.TASK_FAILED for event in seen)
    process_events = [event for event in seen if event.process_id]
    assert process_events
    assert len({event.process_id for event in process_events}) == 1


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


def test_observer_sees_independent_redacted_event_objects():
    seen = []

    class Observer:
        def on_event(self, event):
            seen.append(event)

    workflow = Workflow(
        id="independent-events",
        tasks=(Task(id="task", operation=lambda *_: Result()),),
    )

    execute_workflow(workflow, observers=(Observer(),))

    assert len(seen) > 1
    assert seen[0] is not seen[1]
    assert seen[0].sequence < seen[1].sequence
