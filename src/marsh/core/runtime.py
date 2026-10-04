"""Planning and minimal sequential local execution for the canonical workflow IR."""

from __future__ import annotations

import functools
import inspect
import os
import subprocess
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from marsh.core.artifacts import ArtifactStore, Provenance
from marsh.core.cache import Cache, cache_key_for_task
from marsh.core.identity import execution_id
from marsh.core.domain import (
    ProcessSpec,
    ProcessStatus,
    Result,
    Task,
    Workflow,
    can_transition,
)
from marsh.core.observability import EventType, Observer, RuntimeEvent, emit_event
from marsh.core.policies import ExecutionPolicy, evaluate_policy
from marsh.core.scheduler import AsyncScheduler, ProcessScheduler, ThreadScheduler


def _finalize_result(
    result: Result,
    *,
    workflow_id: str,
    execution_id_value: str | None,
    task_id: str,
    attempt_id: str | None,
    artifact_store: ArtifactStore | None,
) -> Result:
    artifact_refs = []
    if artifact_store is not None:
        if result.stdout:
            artifact_refs.append(
                artifact_store.put(
                    result.stdout,
                    media_type="application/octet-stream",
                )
            )
        if result.stderr:
            artifact_refs.append(
                artifact_store.put(
                    result.stderr,
                    media_type="application/octet-stream",
                )
            )

    provenance = Provenance(
        schema_version=1,
        workflow_id=workflow_id,
        task_id=task_id,
        execution_id=execution_id_value,
        attempt_id=attempt_id,
        output_artifact_refs=tuple(
            ref.digest for ref in artifact_refs
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
    ).to_dict()

    return replace(
        result,
        execution_id=execution_id_value,
        attempt_id=attempt_id,
        artifact_refs=tuple(artifact_refs),
        provenance=provenance,
    )


def _workflow_execution_id(
    workflow: Workflow,
    policy: ExecutionPolicy,
) -> str | None:
    try:
        return execution_id(workflow, policy=policy.to_mapping())
    except (TypeError, ValueError):
        return None


class _LocalProvider:
    """Lazy local provider used only for runtime compatibility."""

    @property
    def capabilities(self):
        from marsh.core.providers import LocalProvider

        return LocalProvider().capabilities

    def create_machine(self):
        from marsh.core.providers import LocalProvider

        return LocalProvider().create_machine()


@dataclass(frozen=True)
class ExecutionPlan:
    """Deterministic workflow order plus tasks initially ready to run."""

    order: tuple[str, ...]
    ready: tuple[str, ...]


def plan_workflow(workflow: Workflow) -> ExecutionPlan:
    """Validate dependencies and return a deterministic graphlib-backed plan."""
    from graphlib import TopologicalSorter

    tasks = {task.id: task for task in workflow.tasks}
    graph = {
        task_id: tuple(sorted(tasks[task_id].dependencies))
        for task_id in sorted(tasks)
    }
    try:
        order = tuple(TopologicalSorter(graph).static_order())
    except ValueError as exc:
        raise ValueError("workflow contains a dependency cycle") from exc

    initial_ready = tuple(
        task_id
        for task_id in sorted(tasks)
        if not tasks[task_id].dependencies
    )
    return ExecutionPlan(order=order, ready=initial_ready)


class LocalProcess:
    """Local subprocess adapter implementing Marsh's portable process contract."""

    def __init__(self, spec: ProcessSpec):
        self.spec = spec
        self._process: subprocess.Popen[bytes] | None = None
        self._status = ProcessStatus.CREATED
        self._result: Result | None = None
        self._cancelled = False
        self._started_at: float | None = None
        self._cancel_requested = False

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
        """Request cancellation; wait() confirms the terminal outcome."""
        self._cancel_requested = True
        if self._status is ProcessStatus.CREATED:
            self._transition(ProcessStatus.CANCELLED)
            self._result = Result(status=ProcessStatus.CANCELLED, metadata={"cancellation": "confirmed"})
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
            return self._finish(stdout, stderr, self._process.returncode, ProcessStatus.TIMED_OUT, "process timed out")

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
    *,
    workflow_id: str = "",
    workflow_execution_id: str = "",
    artifact_store: ArtifactStore | None = None,
) -> Result:
    operation = task.operation
    started_at = time.monotonic()
    idempotent = bool(task.metadata.get("idempotent", True))
    cleanup = task.metadata.get("cleanup")
    if cleanup is not None and not callable(cleanup):
        raise TypeError("task cleanup must be callable when provided")

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
            return _finalize_result(
                Result(
                    status=ProcessStatus.FAILED,
                    error=f"task {task.id!r} requests unsupported resources: {requested}",
                    duration=time.monotonic() - started_at,
                ),
                workflow_id=workflow_id,
                execution_id_value=workflow_execution_id,
                task_id=task.id,
                attempt_id=None,
                artifact_store=artifact_store,
            )

    def run_cleanup(attempt: int) -> tuple[bool, str | None]:
        if cleanup is None or not policy.cleanup.enabled:
            return True, None
        try:
            cleanup(task, attempt)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def finish_attempt(result: Result, attempt: int) -> Result | None:
        cleanup_ok, cleanup_error = run_cleanup(attempt)
        decision = evaluate_policy(
            policy,
            result,
            attempt=attempt,
            idempotent=idempotent,
            cleanup_succeeded=cleanup_ok,
        )
        metadata = {
            **result.metadata,
            "attempt": attempt,
            "attempt_id": f"{task.id}:{attempt}",
            "failure_class": decision.failure_class.value,
            "cleanup_succeeded": cleanup_ok,
        }
        if cleanup_error is not None:
            metadata["cleanup_error"] = cleanup_error
        result = replace(result, metadata=metadata)
        if decision.retry:
            return None
        return _finalize_result(
            result,
            workflow_id=workflow_id,
            execution_id_value=workflow_execution_id,
            task_id=task.id,
            attempt_id=metadata["attempt_id"],
            artifact_store=artifact_store,
        )

    if isinstance(operation, ProcessSpec):
        if policy.timeout is not None:
            operation = replace(operation, timeout=policy.timeout.resolve(operation.timeout))
        attempt = 0
        while True:
            attempt += 1
            process = machine.create_process(operation)
            process.start()
            result = process.wait()
            final = finish_attempt(result, attempt)
            if final is not None:
                return final

    if callable(operation):
        attempt = 0
        while True:
            attempt += 1
            try:
                result = operation(task.inputs, dependency_results)
            except Exception as exc:
                result = Result(status=ProcessStatus.FAILED, error=str(exc), duration=time.monotonic() - started_at)
            if not isinstance(result, Result):
                result = Result(status=ProcessStatus.FAILED, error="task operation must return a Result")
            final = finish_attempt(result, attempt)
            if final is not None:
                return final

    return _finalize_result(
        Result(
            status=ProcessStatus.FAILED,
            error=f"unsupported task operation: {type(operation).__name__}",
            duration=time.monotonic() - started_at,
            metadata={"attempt": 0, "attempt_id": f"{task.id}:0"},
        ),
        workflow_id=workflow_id,
        execution_id_value=workflow_execution_id,
        task_id=task.id,
        attempt_id=f"{task.id}:0",
        artifact_store=artifact_store,
    )

def execute_workflow(
    workflow: Workflow,
    machine: LocalMachine | None = None,
    scheduler: SequentialScheduler | None = None,
    policy: ExecutionPolicy | None = None,
    observers: tuple[Observer, ...] = (),
    cache: Cache | None = None,
    provider=None,
    provider_registry=None,
    artifact_store: ArtifactStore | None = None,
) -> dict[str, Result]:
    """Execute a workflow sequentially through a selected execution provider."""
    if machine is not None and provider is not None:
        raise ValueError("machine and provider cannot both be supplied")
    if provider is not None:
        from marsh.core.providers import ProviderConfig, ProviderRegistry

        registry = provider_registry or ProviderRegistry({"local": _LocalProvider()})
        config = provider if isinstance(provider, ProviderConfig) else ProviderConfig(str(provider))
        machine = registry.resolve(config).create_machine(**dict(config.options))
    else:
        machine = machine or LocalMachine()
    scheduler = scheduler or SequentialScheduler()
    policy = policy or ExecutionPolicy.from_mapping(workflow.policy)
    results: dict[str, Result] = {}
    workflow_execution_id = _workflow_execution_id(workflow, policy)
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
            metadata=(dict(result.metadata) | {"duration": result.duration}) if result is not None else {},
        )
        for observer in observers:
            emit_event(observer, event)

    notify(EventType.WORKFLOW_STARTED)

    if isinstance(scheduler, (AsyncScheduler, ThreadScheduler, ProcessScheduler)):
        if isinstance(scheduler, AsyncScheduler):
            raise TypeError("use execute_workflow_async() with AsyncScheduler")
        if isinstance(scheduler, ProcessScheduler):
            run_task = functools.partial(_execute_process_task, policy=policy)
        else:
            run_task = lambda task, dependencies: _execute_task(
                task,
                machine,
                dependencies,
                policy,
                cache,
                workflow_id=workflow.id,
                workflow_execution_id=workflow_execution_id,
                artifact_store=artifact_store,
            )
        results.update(
            scheduler.execute(
                workflow,
                run_task,
                on_start=lambda task_id: notify(EventType.TASK_STARTED, task_id),
                on_complete=lambda task_id, result: notify(
                    EventType.TASK_TIMED_OUT if result.status is ProcessStatus.TIMED_OUT else EventType.TASK_CANCELLED if result.status is ProcessStatus.CANCELLED else EventType.TASK_FAILED if result.failed else EventType.TASK_COMPLETED,
                    task_id,
                    result,
                ),
                on_blocked=lambda task_id, result: notify(
                    EventType.TASK_SKIPPED,
                    task_id,
                    result,
                ),
                fail_fast=policy.failure.mode == "fail_fast",
            )
        )
        if isinstance(scheduler, ProcessScheduler):
            results = {
                task_id: _finalize_result(
                    result,
                    workflow_id=workflow.id,
                    execution_id_value=workflow_execution_id,
                    task_id=task_id,
                    attempt_id=result.attempt_id or result.metadata.get("attempt_id"),
                    artifact_store=artifact_store,
                )
                for task_id, result in results.items()
            }
        notify(EventType.WORKFLOW_COMPLETED)
        return results

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
            workflow_id=workflow.id,
            workflow_execution_id=workflow_execution_id,
            artifact_store=artifact_store,
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


def _execute_process_task(
    task: Task,
    dependency_results: Mapping[str, Result],
    policy: ExecutionPolicy,
) -> Result:
    """Process-safe callback; no live machine, observer, or cache crosses the boundary."""
    return _execute_task(task, LocalMachine(), dependency_results, policy, None)


async def execute_workflow_async(
    workflow: Workflow,
    scheduler: AsyncScheduler | None = None,
    policy: ExecutionPolicy | None = None,
    observers: tuple[Observer, ...] = (),
    cache: Cache | None = None,
    machine: LocalMachine | None = None,
    artifact_store: ArtifactStore | None = None,
) -> dict[str, Result]:
    """Execute a workflow with bounded asyncio concurrency."""
    scheduler = scheduler or AsyncScheduler()
    policy = policy or ExecutionPolicy.from_mapping(workflow.policy)
    machine = machine or LocalMachine()
    results: dict[str, Result] = {}
    workflow_execution_id = _workflow_execution_id(workflow, policy)
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

    async def run_task(task: Task, dependencies: Mapping[str, Result]) -> Result:
        operation = task.operation
        if callable(operation):
            value = operation(task.inputs, dependencies)
            if inspect.isawaitable(value):
                value = await value
            if isinstance(value, Result):
                result = value
            else:
                result = Result(
                    status=ProcessStatus.FAILED,
                    error="task operation must return a Result",
                )
            return _finalize_result(
                result,
                workflow_id=workflow.id,
                execution_id_value=workflow_execution_id,
                task_id=task.id,
                attempt_id=result.metadata.get("attempt_id", f"{task.id}:1"),
                artifact_store=artifact_store,
            )
        return _execute_task(
            task,
            machine,
            dependencies,
            policy,
            cache,
            workflow_id=workflow.id,
            workflow_execution_id=workflow_execution_id,
            artifact_store=artifact_store,
        )

    notify(EventType.WORKFLOW_STARTED)
    results.update(await scheduler.execute(
        workflow,
        run_task,
        on_start=lambda task_id: notify(EventType.TASK_STARTED, task_id),
        on_complete=lambda task_id, result: notify(
            EventType.TASK_FAILED if result.failed else EventType.TASK_COMPLETED,
            task_id,
            result,
        ),
        on_blocked=lambda task_id, result: notify(
            EventType.TASK_SKIPPED,
            task_id,
            result,
        ),
        fail_fast=policy.failure.mode == "fail_fast",
    ))
    notify(EventType.WORKFLOW_COMPLETED)
    return results
