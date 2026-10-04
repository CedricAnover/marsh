import asyncio
import sys
import threading
import time

import pytest

from marsh.core.domain import ProcessStatus, Result, Task, Workflow
from marsh.core.policies import ExecutionPolicy, FailurePolicy
from marsh.core.runtime import execute_workflow, execute_workflow_async
from marsh.core.scheduler import AsyncScheduler, ProcessScheduler, ThreadScheduler, TaskState


def sleepy(inputs, dependencies):
    time.sleep(inputs["delay"])
    return Result(stdout=inputs["name"].encode())


def process_safe(inputs, dependencies):
    return Result(stdout=str(inputs["value"]).encode())


def process_child(inputs, dependencies):
    return Result(stdout=dependencies["a"].stdout + b"-b")


async def async_sleepy(inputs, dependencies):
    await asyncio.sleep(inputs["delay"])
    return Result(stdout=inputs["name"].encode())


def test_thread_scheduler_runs_independent_tasks_with_hard_bound():
    active = 0
    maximum = 0
    lock = threading.Lock()

    def operation(inputs, dependencies):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.08)
        with lock:
            active -= 1
        return Result(stdout=inputs["name"].encode())

    workflow = Workflow(
        id="parallel",
        tasks=tuple(
            Task(id=name, operation=operation, inputs={"name": name, "delay": 0.08})
            for name in ("a", "b", "c", "d")
        ),
    )
    started = time.monotonic()
    results = execute_workflow(workflow, scheduler=ThreadScheduler(2))
    elapsed = time.monotonic() - started

    assert all(result.ok for result in results.values())
    assert maximum <= 2
    assert elapsed < 0.30


def test_thread_scheduler_respects_dependency_barriers_and_fan_in():
    seen = []

    def operation(inputs, dependencies):
        seen.append(inputs["name"])
        return Result(stdout=(dependencies["a"].stdout + b"-b") if dependencies else inputs["name"].encode())

    workflow = Workflow(
        id="dag",
        tasks=(
            Task(id="c", operation=operation, inputs={"name": "c"}, dependencies=("a", "b")),
            Task(id="b", operation=operation, inputs={"name": "b"}, dependencies=("a",)),
            Task(id="a", operation=operation, inputs={"name": "a"}),
        ),
    )
    results = execute_workflow(workflow, scheduler=ThreadScheduler(2))

    assert seen[0] == "a"
    assert set(seen[1:]) == {"b", "c"}
    assert results["c"].ok


def test_thread_scheduler_marks_dependents_blocked_after_failure():
    def fail(inputs, dependencies):
        return Result(status=ProcessStatus.FAILED, error="boom")

    def unexpected(inputs, dependencies):
        raise AssertionError("blocked task ran")

    workflow = Workflow(
        id="blocked",
        tasks=(
            Task(id="a", operation=fail),
            Task(id="b", operation=unexpected, dependencies=("a",)),
            Task(id="c", operation=lambda *_: Result(stdout=b"independent")),
        ),
    )
    results = execute_workflow(workflow, scheduler=ThreadScheduler(2))

    assert results["a"].failed
    assert results["b"].status is ProcessStatus.SKIPPED
    assert results["c"].ok


def test_fail_fast_cancels_pending_work_but_does_not_claim_running_work_was_cancelled():
    started = threading.Event()
    release = threading.Event()

    def fail(inputs, dependencies):
        return Result(status=ProcessStatus.FAILED, error="boom")

    def running(inputs, dependencies):
        started.set()
        release.wait(1)
        return Result(stdout=b"done")

    workflow = Workflow(
        id="cancel",
        tasks=(
            Task(id="a", operation=fail),
            Task(id="b", operation=running),
            Task(id="c", operation=lambda *_: Result(stdout=b"pending")),
        ),
    )
    scheduler = ThreadScheduler(2)

    def run():
        nonlocal_result[0] = execute_workflow(
            workflow,
            scheduler=scheduler,
            policy=ExecutionPolicy(failure=FailurePolicy("fail_fast")),
        )

    nonlocal_result = [None]
    thread = threading.Thread(target=run)
    thread.start()
    assert started.wait(1)
    release.set()
    thread.join(2)

    results = nonlocal_result[0]
    assert results["a"].failed
    assert "c" not in results or results["c"].status is ProcessStatus.CANCELLED
    assert results["b"].ok


@pytest.mark.asyncio
async def test_async_scheduler_executes_async_operations_with_bound():
    active = 0
    maximum = 0

    async def operation(inputs, dependencies):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.05)
        active -= 1
        return Result(stdout=inputs["name"].encode())

    workflow = Workflow(
        id="async",
        tasks=tuple(
            Task(id=name, operation=operation, inputs={"name": name})
            for name in ("a", "b", "c")
        ),
    )

    results = await execute_workflow_async(workflow, scheduler=AsyncScheduler(2))

    assert all(result.ok for result in results.values())
    assert maximum <= 2


def test_process_scheduler_requires_picklable_executor():
    scheduler = ProcessScheduler(2)
    with pytest.raises(TypeError, match="picklable"):
        scheduler.execute(
            Workflow(id="process", tasks=(Task(id="a", operation=process_safe),)),
            lambda task, dependencies: Result(stdout=b"no"),
        )


def test_process_scheduler_executes_picklable_tasks_and_dependency_results():
    workflow = Workflow(
        id="process",
        tasks=(
            Task(id="b", operation=process_child, dependencies=("a",)),
            Task(id="a", operation=process_safe, inputs={"value": "value"}),
        ),
    )
    results = execute_workflow(workflow, scheduler=ProcessScheduler(2))

    assert results["a"].stdout == b"value"
    assert results["b"].stdout == b"value-b"


def test_scheduler_state_starts_all_tasks_ready():
    workflow = Workflow(
        id="state",
        tasks=(Task(id="a", operation=process_safe), Task(id="b", operation=process_safe)),
    )
    state = __import__("marsh.core.scheduler", fromlist=["SchedulerState"]).SchedulerState.for_workflow(workflow)

    assert state.states == {"a": TaskState.READY, "b": TaskState.READY}
