"""Planning and minimal sequential local execution for the canonical workflow IR."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, replace
from typing import Any, Mapping

from marsh.core.cache import Cache, cache_key_for_task
from marsh.core.domain import (
    ProcessSpec,
    ProcessStatus,
    Result,
    Task,
    Workflow,
    can_transition,
)
from marsh.core.observability import EventType, Observer, RuntimeEvent, emit_event
from marsh.core.policies import ExecutionPolicy


@dataclass(frozen=True)
class ExecutionPlan:
    """Deterministic workflow order plus tasks initially ready to run."""

    order: tuple[str, ...]
    ready: tuple[str, ...]


def plan_workflow(workflow: Workflow) -> ExecutionPlan:
    """Validate dependencies and return a deterministic topological plan."""
    tasks = {task.id: task for task in workflow.tasks}
    indegree = {task.id: len(task.dependencies) for task in workflow.tasks}
    dependents = {task.id: [] for task in workflow.tasks}

    for task in workflow.tasks:
        for dependency in task.dependencies:
            if dependency not in tasks:
                raise ValueError(
                    f"task {task.id!r} has unknown dependency: {dependency}"
                )
            dependents[dependency].append(task.id)

    ready = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
    initial_ready = tuple(ready)
    order = []

    while ready:
        task_id = ready.pop(0)
        order.append(task_id)
        for dependent in sorted(dependents[task_id]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
        ready.sort()

    if len(order) != len(tasks):
        raise ValueError("workflow contains a dependency cycle")

    return ExecutionPlan(order=tuple(order), ready=initial_ready)


class LocalProcess:
    """Local subprocess adapter implementing Marsh's portable process contract."""

    def __init__(self, spec: ProcessSpec):
        self.spec = spec
        self._process: subprocess.Popen[bytes] | None = None
        self._status = ProcessStatus.CREATED
        self._result: Result | None = None
        self._cancelled = False
        self._started_at: float | None = None

    @property
    def status(self) -> ProcessStatus:
        return self._status

    def _transition(self, target: ProcessStatus) -> None:
        if target is self._status:
            return
        if not can_transition(self._status, target):
            raise RuntimeError(
                f"invalid process transition: {self._status.value} -> {target.value}"
            )
        self._status = target

    def start(self) -> None:
        if self._status is not ProcessStatus.CREATED:
            raise RuntimeError(f"cannot start process in {self._status.value} state")

        self._transition(ProcessStatus.STARTING)
        self._started_at = time.monotonic()
        environment = os.environ.copy()
        environment.update(self.spec.environment)

        try:
            self._process = subprocess.Popen(
                (self.spec.executable, *self.spec.arguments),
                stdin=subprocess.PIPE if self.spec.stdin is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.spec.working_directory,
                env=environment,
            )
        except OSError as exc:
            self._transition(ProcessStatus.FAILED)
            self._result = Result(
                status=ProcessStatus.FAILED,
                error=str(exc),
                duration=time.monotonic() - self._started_at,
            )
            return

        self._transition(ProcessStatus.RUNNING)

    def poll(self) -> ProcessStatus:
        if self._process is None:
            return self._status
        if self._status in {
            ProcessStatus.CREATED,
            ProcessStatus.STARTING,
            ProcessStatus.CANCELLED,
            ProcessStatus.TIMED_OUT,
        }:
            return self._status
        code = self._process.poll()
        if code is None:
            self._transition(ProcessStatus.RUNNING)
        elif self._status is ProcessStatus.RUNNING:
            self._transition(
                ProcessStatus.COMPLETED if code == 0 else ProcessStatus.FAILED
            )
        return self._status

    def stop(self) -> None:
        self._terminate(ProcessStatus.CANCELLED)

    def terminate(self) -> None:
        self._terminate(ProcessStatus.CANCELLED)

    def kill(self) -> None:
        self._terminate(ProcessStatus.CANCELLED, force=True)

    def cancel(self) -> None:
        if self._status is ProcessStatus.CREATED:
            self._transition(ProcessStatus.CANCELLED)
            self._result = Result(status=ProcessStatus.CANCELLED)
            return
        self._terminate(ProcessStatus.CANCELLED)

    def _terminate(self, status: ProcessStatus, force: bool = False) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._cancelled = status is ProcessStatus.CANCELLED
        self._transition(ProcessStatus.STOPPING)
        if force:
            self._process.kill()
        else:
            self._process.terminate()

    def wait(self) -> Result:
        if self._result is not None:
            return self._result
        if self._process is None:
            return self._result or Result(
                status=self._status,
                error="process was not started",
            )

        try:
            stdout, stderr = self._process.communicate(
                input=self.spec.stdin,
                timeout=self.spec.timeout,
            )
        except subprocess.TimeoutExpired:
            self._transition(ProcessStatus.TIMED_OUT)
            self._process.kill()
            stdout, stderr = self._process.communicate()
            return self._finish(stdout, stderr, None, ProcessStatus.TIMED_OUT, "process timed out")

        status = (
            ProcessStatus.CANCELLED
            if self._cancelled
            else ProcessStatus.COMPLETED
            if self._process.returncode == 0
            else ProcessStatus.FAILED
        )
        error = (
            None
            if status in {ProcessStatus.COMPLETED, ProcessStatus.CANCELLED}
            else f"process exited with code {self._process.returncode}"
        )
        return self._finish(stdout, stderr, self._process.returncode, status, error)

    def _finish(
        self,
        stdout: bytes,
        stderr: bytes,
        exit_code: int | None,
        status: ProcessStatus,
        error: str | None,
    ) -> Result:
        self._transition(status)
        self._result = Result(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            status=status,
            error=error,
            duration=(
                time.monotonic() - self._started_at
                if self._started_at is not None
                else None
            ),
        )
        return self._result

    def result(self) -> Result:
        return self.wait()


class LocalMachine:
    """Machine adapter that materializes local subprocesses."""

    def create_process(self, spec: ProcessSpec) -> LocalProcess:
        return LocalProcess(spec)


class SequentialScheduler:
    """Scheduler that executes tasks in the deterministic plan order."""

    def schedule(self, workflow: Workflow) -> tuple[Task, ...]:
        plan = plan_workflow(workflow)
        return tuple(workflow.task(task_id) for task_id in plan.order)


def _execute_task(
    task: Task,
    machine: LocalMachine,
    dependency_results: Mapping[str, Result],
    policy: ExecutionPolicy,
    cache: Cache | None = None,
) -> Result:
    operation = task.operation
    started_at = time.monotonic()

    cache_key = None
    if policy.cache.enabled and cache is not None:
        cache_key = cache_key_for_task(
            task,
            dependency_results,
            namespace=policy.cache.namespace,
        )
        if cache_key is not None:
            cached = cache.get(cache_key)
            if cached is not None and cached.ok:
                return cached

    if policy.resources is not None:
        requested = task.metadata.get("resources", {})
        if not policy.resources.supports(requested):
            return Result(
                status=ProcessStatus.FAILED,
                error=f"task {task.id!r} requests unsupported resources: {requested}",
                duration=time.monotonic() - started_at,
            )

    if isinstance(operation, ProcessSpec):
        if policy.timeout is not None:
            operation = replace(
                operation,
                timeout=policy.timeout.resolve(operation.timeout),
            )
        attempts = 0
        while True:
            attempts += 1
            process = machine.create_process(operation)
            process.start()
            result = process.wait()
            if not policy.retry.should_retry(result, attempts):
                return result

    if callable(operation):
        attempts = 0
        while True:
            attempts += 1
            try:
                result = operation(task.inputs, dependency_results)
            except Exception as exc:
                result = Result(
                    status=ProcessStatus.FAILED,
                    error=str(exc),
                    duration=time.monotonic() - started_at,
                )
            if not isinstance(result, Result):
                result = Result(
                    status=ProcessStatus.FAILED,
                    error="task operation must return a Result",
                    duration=time.monotonic() - started_at,
                )
            if not policy.retry.should_retry(result, attempts):
                return result

    return Result(
        status=ProcessStatus.FAILED,
        error=f"unsupported task operation: {type(operation).__name__}",
        duration=time.monotonic() - started_at,
    )


def execute_workflow(
    workflow: Workflow,
    machine: LocalMachine | None = None,
    scheduler: SequentialScheduler | None = None,
    policy: ExecutionPolicy | None = None,
    observers: tuple[Observer, ...] = (),
    cache: Cache | None = None,
) -> dict[str, Result]:
    """Execute a workflow sequentially with explicit, composable policies."""
    machine = machine or LocalMachine()
    scheduler = scheduler or SequentialScheduler()
    policy = policy or ExecutionPolicy()
    results: dict[str, Result] = {}
    sequence = 0

    def notify(event_type: EventType, task_id: str | None = None, result: Result | None = None) -> None:
        nonlocal sequence
        sequence += 1
        event = RuntimeEvent(
            sequence=sequence,
            event_type=event_type,
            workflow_id=workflow.id,
            task_id=task_id,
            status=result.status if result is not None else None,
            metadata={"duration": result.duration} if result is not None else {},
        )
        for observer in observers:
            emit_event(observer, event)

    notify(EventType.WORKFLOW_STARTED)

    for task in scheduler.schedule(workflow):
        failed_dependencies = [
            dependency
            for dependency in task.dependencies
            if results[dependency].failed
            or results[dependency].status is not ProcessStatus.COMPLETED
        ]
        notify(EventType.TASK_STARTED, task.id)
        if failed_dependencies:
            dependency = failed_dependencies[0]
            results[task.id] = Result(
                status=ProcessStatus.SKIPPED,
                error=f"dependency failed: {dependency}",
            )
            notify(EventType.TASK_SKIPPED, task.id, results[task.id])
            continue

        result = _execute_task(
            task,
            machine,
            {dependency: results[dependency] for dependency in task.dependencies},
            policy,
            cache,
        )
        results[task.id] = result
        notify(
            EventType.TASK_FAILED if result.failed else EventType.TASK_COMPLETED,
            task.id,
            result,
        )
        if policy.cache.enabled and cache is not None and result.ok:
            cache_key = cache_key_for_task(
                task,
                {dependency: results[dependency] for dependency in task.dependencies},
                namespace=policy.cache.namespace,
            )
            if cache_key is not None:
                cache.put(cache_key, result)

        if result.failed and not policy.failure.should_continue(result):
            break

    notify(EventType.WORKFLOW_COMPLETED)
    return results
