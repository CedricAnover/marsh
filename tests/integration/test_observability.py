import sys

from marsh.core.domain import ProcessSpec, ProcessStatus, Task, Workflow
from marsh.core.observability import EventType
from marsh.core.runtime import execute_workflow


def test_local_process_success_produces_correlated_lifecycle_evidence():
    events = []

    class Observer:
        def on_event(self, event):
            events.append(event)

    workflow = Workflow(
        id="integration-success",
        tasks=(
            Task(
                id="task",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "print('integration-ok')"),
                ),
            ),
        ),
    )

    results = execute_workflow(workflow, observers=(Observer(),))
    task_events = [event for event in events if event.task_id == "task"]

    assert results["task"].status is ProcessStatus.COMPLETED
    assert [event.event_type for event in task_events] == [
        EventType.ATTEMPT_STARTED,
        EventType.PROCESS_CREATED,
        EventType.PROCESS_STARTED,
        EventType.PROCESS_RUNNING,
        EventType.PROCESS_COMPLETED,
        EventType.ATTEMPT_COMPLETED,
        EventType.RESULT_MATERIALIZED,
        EventType.TASK_COMPLETED,
    ]
    assert all(event.execution_id == results["task"].execution_id for event in task_events)
    assert len({event.attempt_id for event in task_events if event.attempt_id}) == 1
    assert len({event.process_id for event in task_events if event.process_id}) == 1


def test_local_process_timeout_is_observable_without_changing_result_semantics():
    events = []

    class Observer:
        def on_event(self, event):
            events.append(event)

    workflow = Workflow(
        id="integration-timeout",
        tasks=(
            Task(
                id="task",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "import time; time.sleep(1)"),
                    timeout=0.02,
                ),
            ),
        ),
    )

    result = execute_workflow(workflow, observers=(Observer(),))["task"]

    assert result.status is ProcessStatus.TIMED_OUT
    assert any(
        event.event_type is EventType.PROCESS_TIMED_OUT
        for event in events
        if event.task_id == "task"
    )
    assert any(
        event.event_type is EventType.TASK_TIMED_OUT
        for event in events
        if event.task_id == "task"
    )


def test_secret_in_process_environment_never_reaches_observer():
    events = []

    class Observer:
        def on_event(self, event):
            events.append(event)

    workflow = Workflow(
        id="integration-redaction",
        tasks=(
            Task(
                id="task",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "print('safe')"),
                    environment={"API_TOKEN": "integration-secret"},
                ),
            ),
        ),
    )

    result = execute_workflow(workflow, observers=(Observer(),))["task"]

    assert result.ok
    serialized = "\\n".join(str(event.to_dict()) for event in events)
    assert "integration-secret" not in serialized
