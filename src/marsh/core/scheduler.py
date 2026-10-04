"""Deterministic bounded-concurrency schedulers for the canonical workflow runtime."""

from __future__ import annotations

import asyncio
import inspect
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping

from marsh.core.domain import ProcessStatus, Result, Task, Workflow


class TaskState(str, Enum):
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass
class SchedulerState:
    """Mutable scheduling state owned by one workflow execution."""

    states: dict[str, TaskState]
    results: dict[str, Result] = field(default_factory=dict)

    @classmethod
    def for_workflow(cls, workflow: Workflow) -> "SchedulerState":
        return cls({task.id: TaskState.READY for task in workflow.tasks})

    def terminal(self, task_id: str) -> bool:
        return self.states[task_id] in {
            TaskState.SUCCEEDED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.BLOCKED,
        }

    def dependencies_succeeded(self, task: Task) -> bool:
        return all(self.states[d] is TaskState.SUCCEEDED for d in task.dependencies)

    def dependency_failed(self, task: Task) -> str | None:
        for dependency in task.dependencies:
            if self.states[dependency] in {
                TaskState.FAILED,
                TaskState.CANCELLED,
                TaskState.BLOCKED,
            }:
                return dependency
        return None

    def mark_completed(self, task_id: str, result: Result) -> None:
        self.results[task_id] = result
        if result.ok:
            self.states[task_id] = TaskState.SUCCEEDED
        elif result.status.value == "cancelled":
            self.states[task_id] = TaskState.CANCELLED
        else:
            self.states[task_id] = TaskState.FAILED


RunTask = Callable[[Task, Mapping[str, Result]], Result]
AsyncRunTask = Callable[[Task, Mapping[str, Result]], Awaitable[Result] | Result]
OnStart = Callable[[str], None]
OnComplete = Callable[[str, Result], None]
OnBlocked = Callable[[str, Result], None]


class ConcurrentScheduler:
    """Shared deterministic readiness state machine for bounded schedulers."""

    def __init__(self, max_concurrency: int = 1) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.max_concurrency = max_concurrency
        self._cancel_requested = False

    def cancel(self) -> None:
        """Cancel work that has not started; running work follows executor semantics."""
        self._cancel_requested = True

    def reset(self) -> None:
        self._cancel_requested = False

    def schedule(self, workflow: Workflow) -> tuple[Task, ...]:
        """Return deterministic topological order for Scheduler compatibility."""
        from marsh.core.runtime import plan_workflow

        return tuple(workflow.task(task_id) for task_id in plan_workflow(workflow).order)

    @staticmethod
    def _ready_tasks(workflow: Workflow, state: SchedulerState) -> list[Task]:
        ready = []
        for task in sorted(workflow.tasks, key=lambda item: item.id):
            if state.states[task.id] is not TaskState.READY:
                continue
            if state.dependencies_succeeded(task):
                ready.append(task)
        return ready

    @staticmethod
    def _block_unrunnable(workflow: Workflow, state: SchedulerState) -> bool:
        changed = False
        for task in sorted(workflow.tasks, key=lambda item: item.id):
            if state.states[task.id] is not TaskState.READY:
                continue
            dependency = state.dependency_failed(task)
            if dependency is not None:
                state.states[task.id] = TaskState.BLOCKED
                result = Result(
                    status=ProcessStatus.SKIPPED,
                    error=f"dependency failed: {dependency}",
                )
                state.results[task.id] = result
                if on_blocked is not None:
                    on_blocked(task.id, result)
                changed = True
        return changed

    def _prepare_dispatch(
        self,
        workflow: Workflow,
        state: SchedulerState,
        running: int,
        on_start: OnStart | None,
        on_blocked: OnBlocked | None,
    ) -> list[Task]:
        self._block_unrunnable(workflow, state)
        if self._cancel_requested:
            for task in workflow.tasks:
                if state.states[task.id] is TaskState.READY:
                    state.states[task.id] = TaskState.CANCELLED
                    state.results[task.id] = Result(status=ProcessStatus.CANCELLED)
            return []
        capacity = self.max_concurrency - running
        dispatch = self._ready_tasks(workflow, state)[: max(0, capacity)]
        for task in dispatch:
            state.states[task.id] = TaskState.RUNNING
            if on_start is not None:
                on_start(task.id)
        return dispatch


class AsyncScheduler(ConcurrentScheduler):
    """Asyncio scheduler with deterministic readiness and bounded overlap."""

    async def execute(
        self,
        workflow: Workflow,
        run_task: AsyncRunTask,
        *,
        on_start: OnStart | None = None,
        on_complete: OnComplete | None = None,
        on_blocked: OnBlocked | None = None,
        fail_fast: bool = False,
    ) -> dict[str, Result]:
        self.reset()
        state = SchedulerState.for_workflow(workflow)
        running: dict[asyncio.Task[Result], str] = {}

        while not all(state.terminal(task.id) for task in workflow.tasks):
            for task in self._prepare_dispatch(workflow, state, len(running), on_start, on_blocked):
                dependencies = {d: state.results[d] for d in task.dependencies}
                future = asyncio.create_task(run_task(task, dependencies))
                running[future] = task.id

            if not running:
                if self._cancel_requested:
                    break
                if not self._block_unrunnable(workflow, state):
                    unresolved = [
                        task.id for task in workflow.tasks if state.states[task.id] is TaskState.READY
                    ]
                    if unresolved:
                        raise RuntimeError(f"scheduler deadlock: {unresolved}")
                continue

            done, _ = await asyncio.wait(
                tuple(running),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for future in sorted(done, key=lambda item: running[item]):
                task_id = running.pop(future)
                try:
                    result = future.result()
                except asyncio.CancelledError:
                    from marsh.core.domain import ProcessStatus

                    result = Result(status=ProcessStatus.CANCELLED)
                except Exception as exc:
                    from marsh.core.domain import ProcessStatus

                    result = Result(status=ProcessStatus.FAILED, error=str(exc))
                state.mark_completed(task_id, result)
                if on_complete is not None:
                    on_complete(task_id, result)
                if fail_fast and result.failed:
                    self._cancel_requested = True

            if self._cancel_requested and running:
                pending = []
                for future, task_id in list(running.items()):
                    if future.cancel():
                        running.pop(future)
                        result = Result(status=ProcessStatus.CANCELLED)
                        state.mark_completed(task_id, result)
                        if on_complete is not None:
                            on_complete(task_id, result)
                    else:
                        pending.append(future)
                if pending:
                    done, _ = await asyncio.wait(tuple(pending))
                    for future in sorted(done, key=lambda item: running[item]):
                        task_id = running.pop(future)
                        try:
                            result = future.result()
                        except asyncio.CancelledError:
                            result = Result(status=ProcessStatus.CANCELLED)
                        except Exception as exc:
                            result = Result(status=ProcessStatus.FAILED, error=str(exc))
                        state.mark_completed(task_id, result)
                        if on_complete is not None:
                            on_complete(task_id, result)

        return state.results


class ExecutorScheduler(ConcurrentScheduler):
    """Thread/process scheduler sharing the same readiness state machine."""

    executor_type = ThreadPoolExecutor

    def execute(
        self,
        workflow: Workflow,
        run_task: RunTask,
        *,
        on_start: OnStart | None = None,
        on_complete: OnComplete | None = None,
        on_blocked: OnBlocked | None = None,
        fail_fast: bool = False,
    ) -> dict[str, Result]:
        self.reset()
        state = SchedulerState.for_workflow(workflow)
        running: dict[Future[Result], str] = {}

        with self.executor_type(max_workers=self.max_concurrency) as executor:
            while not all(state.terminal(task.id) for task in workflow.tasks):
                for task in self._prepare_dispatch(workflow, state, len(running), on_start, on_blocked):
                    dependencies = {d: state.results[d] for d in task.dependencies}
                    running[executor.submit(run_task, task, dependencies)] = task.id

                if not running:
                    if self._cancel_requested:
                        break
                    if not self._block_unrunnable(workflow, state):
                        unresolved = [
                            task.id for task in workflow.tasks if state.states[task.id] is TaskState.READY
                        ]
                        if unresolved:
                            raise RuntimeError(f"scheduler deadlock: {unresolved}")
                    continue

                done, _ = wait(tuple(running), return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda item: running[item]):
                    task_id = running.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        from marsh.core.domain import ProcessStatus

                        result = Result(status=ProcessStatus.FAILED, error=str(exc))
                    state.mark_completed(task_id, result)
                    if on_complete is not None:
                        on_complete(task_id, result)
                    if fail_fast and result.failed:
                        self._cancel_requested = True

                if self._cancel_requested:
                    for future, task_id in list(running.items()):
                        if future.cancel():
                            running.pop(future)
                            from marsh.core.domain import ProcessStatus

                            result = Result(status=ProcessStatus.CANCELLED)
                            state.mark_completed(task_id, result)
                            if on_complete is not None:
                                on_complete(task_id, result)
                    if running:
                        done, _ = wait(tuple(running))
                        for future in done:
                            task_id = running.pop(future)
                            try:
                                result = future.result()
                            except Exception as exc:
                                from marsh.core.domain import ProcessStatus

                                result = Result(status=ProcessStatus.FAILED, error=str(exc))
                            state.mark_completed(task_id, result)
                            if on_complete is not None:
                                on_complete(task_id, result)

        return state.results


class ThreadScheduler(ExecutorScheduler):
    """Bounded scheduler backed by ThreadPoolExecutor."""


def _run_process_task(
    task: Task,
    dependencies: Mapping[str, Result],
    run_task: RunTask,
) -> Result:
    return run_task(task, dependencies)


class ProcessScheduler(ExecutorScheduler):
    """Bounded scheduler backed by ProcessPoolExecutor.

    The task, dependency results, and execution callback must be serializable.
    """

    executor_type = ProcessPoolExecutor

    def execute(
        self,
        workflow: Workflow,
        run_task: RunTask,
        *,
        on_start: OnStart | None = None,
        on_complete: OnComplete | None = None,
        on_blocked: OnBlocked | None = None,
        fail_fast: bool = False,
    ) -> dict[str, Result]:
        if not _is_picklable(run_task):
            raise TypeError("process scheduler requires a picklable task executor")
        return super().execute(
            workflow,
            run_task,
            on_start=on_start,
            on_complete=on_complete,
            on_blocked=on_blocked,
            fail_fast=fail_fast,
        )


def _is_picklable(value: Any) -> bool:
    import pickle

    try:
        pickle.dumps(value)
    except (pickle.PicklingError, TypeError, AttributeError):
        return False
    return True
