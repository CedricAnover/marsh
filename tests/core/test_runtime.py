import sys
import time

import pytest

from marsh.core.domain import ProcessSpec, ProcessStatus, Result, Task, Workflow
from marsh.core.cache import CachePolicy, MemoryCache
from marsh.core.observability import EventType
from marsh.core.policies import ExecutionPolicy, FailurePolicy, ResourcePolicy, RetryPolicy, TimeoutPolicy
from marsh.core.runtime import (
    LocalMachine,
    SequentialScheduler,
    execute_workflow,
    plan_workflow,
)


def test_plan_workflow_is_deterministic_and_reports_readiness():
    workflow = Workflow(
        id="plan",
        tasks=(
            Task(id="c", operation="noop", dependencies=("a",)),
            Task(id="a", operation="noop"),
            Task(id="b", operation="noop"),
        ),
    )

    plan = plan_workflow(workflow)

    assert plan.order == ("a", "b", "c")
    assert plan.ready == ("a", "b")


def test_sequential_scheduler_uses_planned_order():
    workflow = Workflow(
        id="schedule",
        tasks=(
            Task(id="c", operation="noop", dependencies=("a",)),
            Task(id="a", operation="noop"),
            Task(id="b", operation="noop"),
        ),
    )

    assert tuple(task.id for task in SequentialScheduler().schedule(workflow)) == (
        "a",
        "b",
        "c",
    )


def test_local_machine_executes_process_spec_and_preserves_stderr():
    spec = ProcessSpec(
        executable=sys.executable,
        arguments=("-c", "import sys; print('ok'); print('note', file=sys.stderr)"),
    )

    result = LocalMachine().create_process(spec)
    result.start()
    outcome = result.wait()

    assert outcome.status is ProcessStatus.COMPLETED
    assert outcome.exit_code == 0
    assert outcome.stdout.strip() == b"ok"
    assert outcome.stderr.strip() == b"note"
    assert outcome.ok


def test_local_machine_maps_nonzero_exit_to_failed_result():
    spec = ProcessSpec(executable=sys.executable, arguments=("-c", "raise SystemExit(3)"))

    process = LocalMachine().create_process(spec)
    process.start()

    outcome = process.wait()

    assert outcome.status is ProcessStatus.FAILED
    assert outcome.exit_code == 3
    assert outcome.failed


def test_execute_workflow_runs_in_dependency_order_and_passes_results():
    seen = []

    def producer(inputs, dependencies):
        seen.append("producer")
        return Result(stdout=b"value", metadata={"value": "42"})

    def consumer(inputs, dependencies):
        seen.append("consumer")
        assert dependencies["producer"].stdout == b"value"
        return Result(stdout=dependencies["producer"].stdout + b"-consumed")

    workflow = Workflow(
        id="data",
        tasks=(
            Task(id="consumer", operation=consumer, dependencies=("producer",)),
            Task(id="producer", operation=producer),
        ),
    )

    results = execute_workflow(workflow)

    assert seen == ["producer", "consumer"]
    assert results["consumer"].stdout == b"value-consumed"
    assert results["consumer"].status is ProcessStatus.COMPLETED


def test_execute_workflow_skips_dependents_after_failure_but_runs_independent_tasks():
    seen = []

    def fail(inputs, dependencies):
        seen.append("fail")
        return Result(status=ProcessStatus.FAILED, error="boom")

    def skipped(inputs, dependencies):
        seen.append("skipped")
        return Result(stdout=b"unexpected")

    def independent(inputs, dependencies):
        seen.append("independent")
        return Result(stdout=b"ok")

    workflow = Workflow(
        id="failure",
        tasks=(
            Task(id="skipped", operation=skipped, dependencies=("fail",)),
            Task(id="fail", operation=fail),
            Task(id="independent", operation=independent),
        ),
    )

    results = execute_workflow(workflow)

    assert results["fail"].status is ProcessStatus.FAILED
    assert results["skipped"].status is ProcessStatus.SKIPPED
    assert results["skipped"].error == "dependency failed: fail"
    assert results["independent"].status is ProcessStatus.COMPLETED
    assert seen == ["fail", "independent"]


def test_execute_workflow_supports_local_process_spec_operations():
    workflow = Workflow(
        id="local",
        tasks=(
            Task(
                id="hello",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "print('hello')"),
                ),
            ),
        ),
    )

    results = execute_workflow(workflow)

    assert results["hello"].status is ProcessStatus.COMPLETED
    assert results["hello"].stdout.strip() == b"hello"


def test_local_process_timeout_is_structured():
    spec = ProcessSpec(
        executable=sys.executable,
        arguments=("-c", "import time; time.sleep(2)"),
        timeout=0.05,
    )

    process = LocalMachine().create_process(spec)
    process.start()
    outcome = process.wait()

    assert outcome.status is ProcessStatus.TIMED_OUT
    assert outcome.failed


def test_local_process_can_be_cancelled():
    spec = ProcessSpec(
        executable=sys.executable,
        arguments=("-c", "import time; time.sleep(2)"),
    )

    process = LocalMachine().create_process(spec)
    process.start()
    process.cancel()

    outcome = process.wait()

    assert outcome.status is ProcessStatus.CANCELLED
    assert outcome.failed is False

def test_execute_workflow_applies_retry_timeout_and_resource_policies():
    attempts = []

    def operation(inputs, dependencies):
        attempts.append(1)
        if len(attempts) == 1:
            return Result(status=ProcessStatus.FAILED, error="transient")
        return Result(stdout=b"ok")

    workflow = Workflow(
        id="policy",
        tasks=(Task(id="task", operation=operation, metadata={"resources": {"cpu": 1}}),),
    )

    results = execute_workflow(
        workflow,
        policy=ExecutionPolicy(
            retry=RetryPolicy(max_attempts=2),
            timeout=TimeoutPolicy(1.0),
            resources=ResourcePolicy({"cpu": 2}),
        ),
    )

    assert attempts == [1, 1]
    assert results["task"].status is ProcessStatus.COMPLETED


def test_execute_workflow_rejects_unsupported_task_resources():
    workflow = Workflow(
        id="resource",
        tasks=(Task(id="task", operation=lambda *_: Result(), metadata={"resources": {"gpu": 1}}),),
    )

    results = execute_workflow(
        workflow,
        policy=ExecutionPolicy(resources=ResourcePolicy({"cpu": 2})),
    )

    assert results["task"].status is ProcessStatus.FAILED
    assert "resources" in results["task"].error

def test_local_process_exposes_explicit_lifecycle_states():
    spec = ProcessSpec(executable=sys.executable, arguments=("-c", "print('ok')"))
    process = LocalMachine().create_process(spec)

    assert process.status is ProcessStatus.CREATED
    process.start()
    assert process.status is ProcessStatus.RUNNING
    assert process.poll() in {ProcessStatus.RUNNING, ProcessStatus.COMPLETED}
    outcome = process.wait()
    assert outcome.status is ProcessStatus.COMPLETED
    assert process.status is ProcessStatus.COMPLETED

def test_execute_workflow_emits_ordered_observer_events_and_ignores_observer_errors():
    events = []

    class Observer:
        def on_event(self, event):
            events.append(event)
            if event.event_type is EventType.TASK_COMPLETED:
                raise RuntimeError("observer must not affect execution")

    workflow = Workflow(
        id="events",
        tasks=(Task(id="task", operation=lambda *_: Result(stdout=b"ok")),),
    )

    results = execute_workflow(workflow, observers=(Observer(),))

    assert results["task"].ok
    assert [event.event_type for event in events] == [
        EventType.WORKFLOW_STARTED,
        EventType.PROVIDER_SELECTED,
        EventType.TASK_STARTED,
        EventType.ATTEMPT_STARTED,
        EventType.ATTEMPT_COMPLETED,
        EventType.RESULT_MATERIALIZED,
        EventType.TASK_COMPLETED,
        EventType.WORKFLOW_COMPLETED,
    ]
    assert [event.sequence for event in events] == list(range(1, 9))


def test_execute_workflow_uses_opt_in_cache_only_for_successful_results():
    workflow = Workflow(
        id="cache",
        tasks=(
            Task(
                id="task",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "print('cached')"),
                ),
            ),
        ),
    )
    cache = MemoryCache()
    policy = ExecutionPolicy(cache=CachePolicy(enabled=True))

    first = execute_workflow(workflow, policy=policy, cache=cache)
    second = execute_workflow(workflow, policy=policy, cache=cache)

    assert first["task"] == second["task"]
    assert first["task"].stdout.strip() == b"cached"


def test_execute_workflow_accepts_replacement_scheduler_and_machine_contracts():
    seen = []

    class FakeProcess:
        def __init__(self, result):
            self.result = result

        def start(self):
            seen.append("start")

        def wait(self):
            seen.append("wait")
            return self.result

    class FakeMachine:
        def create_process(self, spec):
            seen.append(("machine", spec.executable))
            return FakeProcess(Result(stdout=b"fake"))

    class FakeScheduler:
        def schedule(self, workflow):
            seen.append("schedule")
            return tuple(reversed(workflow.tasks))

    workflow = Workflow(
        id="replaceable",
        tasks=(
            Task(id="a", operation=ProcessSpec(executable="fake-a")),
            Task(id="b", operation=ProcessSpec(executable="fake-b")),
        ),
    )

    results = execute_workflow(
        workflow,
        machine=FakeMachine(),
        scheduler=FakeScheduler(),
    )

    assert seen == [
        "schedule",
        ("machine", "fake-b"),
        "start",
        "wait",
        ("machine", "fake-a"),
        "start",
        "wait",
    ]
    assert all(result.ok for result in results.values())


def test_execute_workflow_fail_fast_stops_after_first_failed_task():
    seen = []

    def fail(inputs, dependencies):
        seen.append("fail")
        return Result(status=ProcessStatus.FAILED, error="boom")

    def independent(inputs, dependencies):
        seen.append("independent")
        return Result(stdout=b"ok")

    workflow = Workflow(
        id="fail-fast",
        tasks=(
            Task(id="fail", operation=fail),
            Task(id="independent", operation=independent),
        ),
    )

    results = execute_workflow(
        workflow,
        policy=ExecutionPolicy(failure=FailurePolicy("fail_fast")),
    )

    assert seen == ["fail"]
    assert results["fail"].status is ProcessStatus.FAILED
    assert "independent" not in results
