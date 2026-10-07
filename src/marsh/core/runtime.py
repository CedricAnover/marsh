"""Planning and minimal sequential local execution for the canonical workflow IR."""

from __future__ import annotations

import functools
import inspect
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from marsh.core.artifacts import ArtifactStore, Provenance
from marsh.core.cache import Cache, cache_key_for_task
from marsh.core.identity import execution_id
from marsh.core.domain import (
    ProcessSpec,
    ProcessIdentity,
    ProcessStatus,
    Result,
    Task,
    Workflow,
    can_transition,
)
from marsh.core.observability import (
    Diagnostic,
    DiagnosticCode,
    EventType,
    Observer,
    RuntimeEvent,
    emit_diagnostic,
    emit_event,
)
from marsh.core.policies import ExecutionPolicy, evaluate_policy
from marsh.core.remote import MachineConnection
from marsh.core.scheduler import AsyncScheduler, ProcessScheduler, ThreadScheduler
from marsh.core.providers import ProviderConfig, ProviderRegistry


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
) -> str:
    """Return deterministic semantic identity or a per-invocation fallback."""
    try:
        value = execution_id(workflow, policy=policy.to_mapping())
    except (TypeError, ValueError):
        value = None
    return value or uuid.uuid4().hex


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
        self._identity = ProcessIdentity(uuid.uuid4().hex)
        self._result: Result | None = None
        self._cancelled = False
        self._started_at: float | None = None
        self._cancel_requested = False

    @property
    def status(self) -> ProcessStatus:
        return self._status

    @property
    def process_id(self) -> str:
        return self._identity.value

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
            metadata={
                "cancellation": "confirmed" if status is ProcessStatus.CANCELLED else "not_requested" if not self._cancel_requested else "requested",
                "timeout": status is ProcessStatus.TIMED_OUT,
            },
        )
        return self._result

    def result(self) -> Result:
        return self.wait()


class LocalMachine:
    """Machine adapter that materializes local subprocesses."""

    @property
    def machine_id(self) -> str:
        return "local"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset(
            {
                "machine.create",
                "process.start",
                "process.wait",
                "process.poll",
                "process.stop",
                "process.terminate",
                "process.kill",
                "process.cancel",
                "process.result",
            }
        )

    @property
    def connection(self) -> MachineConnection | None:
        return None

    def create_process(self, spec: ProcessSpec) -> LocalProcess:
        return LocalProcess(spec)


class SequentialScheduler:
    """Scheduler that executes tasks in the deterministic plan order."""

    def schedule(self, workflow: Workflow) -> tuple[Task, ...]:
        plan = plan_workflow(workflow)
        return tuple(workflow.task(task_id) for task_id in plan.order)


def _task_terminal_event(result: Result) -> EventType:
    """Map a canonical task result to the stable task observation vocabulary."""
    if result.status is ProcessStatus.TIMED_OUT:
        return EventType.TASK_TIMED_OUT
    if result.status is ProcessStatus.CANCELLED:
        return EventType.TASK_CANCELLED
    return EventType.TASK_FAILED if result.failed else EventType.TASK_COMPLETED


def _execute_task(
    task: Task,
    machine: LocalMachine,
    dependency_results: Mapping[str, Result],
    policy: ExecutionPolicy,
    cache: Cache | None = None,
    *,
    workflow_id: str = "",
    workflow_execution_id: str | None = None,
    artifact_store: ArtifactStore | None = None,
    provider_id: str | None = None,
    notify=None,
) -> Result:
    """Execute one task while projecting canonical attempt/process evidence."""
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
            result = _finalize_result(
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
            if notify is not None:
                notify(
                    EventType.PROVIDER_REJECTED,
                    task_id=task.id,
                    result=result,
                    provider_id=provider_id,
                    metadata={"reason": "unsupported_resources", "requested": requested},
                )
            return result

    def run_cleanup(attempt: int) -> tuple[bool, str | None]:
        if cleanup is None or not policy.cleanup.enabled:
            return True, None
        try:
            cleanup(task, attempt)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def finish_attempt(result: Result, attempt: int, attempt_id: str, process_id: str | None = None) -> Result | None:
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
            "attempt_id": attempt_id,
            "failure_class": decision.failure_class.value,
            "cleanup_succeeded": cleanup_ok,
        }
        if cleanup_error is not None:
            metadata["cleanup_error"] = cleanup_error
            if notify is not None:
                notify(
                    EventType.OBSERVATION_CONFLICTING,
                    task_id=task.id,
                    attempt_id=attempt_id,
                    process_id=process_id,
                    result=result,
                    provider_id=provider_id,
                    metadata={"diagnostic_code": DiagnosticCode.CLEANUP_FAILURE.value},
                )
        result = replace(result, metadata=metadata)
        if notify is not None:
            notify(
                EventType.ATTEMPT_COMPLETED,
                task_id=task.id,
                attempt_id=attempt_id,
                process_id=process_id,
                result=result,
                provider_id=provider_id,
            )
        if decision.retry:
            if notify is not None:
                notify(
                    EventType.TASK_RETRY_SCHEDULED,
                    task_id=task.id,
                    attempt_id=attempt_id,
                    process_id=process_id,
                    result=result,
                    provider_id=provider_id,
                    metadata={"next_attempt": attempt + 1},
                )
            return None
        final = _finalize_result(
            result,
            workflow_id=workflow_id,
            execution_id_value=workflow_execution_id,
            task_id=task.id,
            attempt_id=attempt_id,
            artifact_store=artifact_store,
        )
        if notify is not None:
            notify(
                EventType.RESULT_MATERIALIZED,
                task_id=task.id,
                attempt_id=attempt_id,
                process_id=process_id,
                result=final,
                provider_id=provider_id,
            )
        return final

    if isinstance(operation, ProcessSpec):
        if policy.timeout is not None:
            operation = replace(operation, timeout=policy.timeout.resolve(operation.timeout))
        attempt = 0
        while True:
            attempt += 1
            attempt_id = f"{task.id}:{attempt}"
            if notify is not None:
                notify(
                    EventType.ATTEMPT_STARTED,
                    task_id=task.id,
                    attempt_id=attempt_id,
                    provider_id=provider_id,
                )
            process = machine.create_process(operation)
            if notify is not None:
                notify(
                    EventType.PROCESS_CREATED,
                    task_id=task.id,
                    attempt_id=attempt_id,
                    process_id=getattr(process, "process_id", None),
                    provider_id=provider_id,
                    metadata={"process_handle": getattr(process, "process_id", None)},
                )
            process.start()
            if notify is not None:
                notify(
                    EventType.PROCESS_STARTED,
                    task_id=task.id,
                    attempt_id=attempt_id,
                    process_id=getattr(process, "process_id", None),
                    provider_id=provider_id,
                    status=process.status,
                )
                if process.status is ProcessStatus.RUNNING:
                    notify(
                        EventType.PROCESS_RUNNING,
                        task_id=task.id,
                        attempt_id=attempt_id,
                        process_id=getattr(process, "process_id", None),
                        provider_id=provider_id,
                        status=process.status,
                    )
            result = process.wait()
            terminal_event = {
                ProcessStatus.COMPLETED: EventType.PROCESS_COMPLETED,
                ProcessStatus.FAILED: EventType.PROCESS_FAILED,
                ProcessStatus.CANCELLED: EventType.PROCESS_CANCELLED,
                ProcessStatus.TIMED_OUT: EventType.PROCESS_TIMED_OUT,
            }.get(result.status, EventType.PROCESS_UNKNOWN)
            if notify is not None:
                notify(
                    terminal_event,
                    task_id=task.id,
                    attempt_id=attempt_id,
                    process_id=getattr(process, "process_id", None),
                    provider_id=provider_id,
                    status=result.status,
                    result=result,
                )
            final = finish_attempt(result, attempt, attempt_id, getattr(process, "process_id", None))
            if final is not None:
                return final

    if callable(operation):
        attempt = 0
        while True:
            attempt += 1
            attempt_id = f"{task.id}:{attempt}"
            if notify is not None:
                notify(
                    EventType.ATTEMPT_STARTED,
                    task_id=task.id,
                    attempt_id=attempt_id,
                    provider_id=provider_id,
                )
            try:
                result = operation(task.inputs, dependency_results)
            except Exception as exc:
                result = Result(status=ProcessStatus.FAILED, error=str(exc), duration=time.monotonic() - started_at)
                if notify is not None:
                    notify(
                        EventType.OBSERVATION_CONFLICTING,
                        task_id=task.id,
                        attempt_id=attempt_id,
                        provider_id=provider_id,
                        result=result,
                        metadata={"diagnostic_code": DiagnosticCode.PROVIDER_FAILURE.value},
                    )
            if not isinstance(result, Result):
                result = Result(status=ProcessStatus.FAILED, error="task operation must return a Result")
            final = finish_attempt(result, attempt, attempt_id)
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
    if provider is not None:
        provider_id = getattr(provider, "name", None) if not isinstance(provider, ProviderConfig) else provider.name
    elif isinstance(machine, LocalMachine):
        provider_id = "local"
    else:
        provider_id = None

    def notify(
        event_type: EventType,
        task_id: str | None = None,
        result: Result | None = None,
        *,
        execution_id_value: str | None = None,
        attempt_id: str | None = None,
        process_id: str | None = None,
        provider_id: str | None = provider_id,
        status: ProcessStatus | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        nonlocal sequence
        sequence += 1
        effective_status = status if status is not None else result.status if result is not None else None
        event = RuntimeEvent(
            sequence=sequence,
            event_type=event_type,
            workflow_id=workflow.id,
            task_id=task_id,
            execution_id=workflow_execution_id if execution_id_value is None else execution_id_value,
            attempt_id=attempt_id or (result.attempt_id if result is not None else None),
            provider_id=provider_id,
            process_id=process_id,
            status=effective_status,
            metadata=(dict(result.metadata) | {"duration": result.duration} | dict(metadata or {})) if result is not None else dict(metadata or {}),
        )
        for observer in observers:
            emit_event(observer, event)
            if hasattr(observer, "on_diagnostic") and metadata and metadata.get("diagnostic_code"):
                try:
                    code = DiagnosticCode(str(metadata["diagnostic_code"]))
                except ValueError:
                    code = DiagnosticCode.OBSERVATION_FAILURE
                emit_diagnostic(
                    observer,
                    Diagnostic(
                        code=code,
                        message=str(metadata.get("diagnostic_message", event_type.value)),
                        workflow_id=workflow.id,
                        execution_id=workflow_execution_id,
                        task_id=task_id,
                        attempt_id=attempt_id,
                        provider_id=provider_id,
                        process_id=process_id,
                        details=metadata,
                    ),
                )

    notify(EventType.WORKFLOW_STARTED)
    if provider_id is not None:
        notify(EventType.PROVIDER_SELECTED, metadata={"provider": provider_id})

    if isinstance(scheduler, (AsyncScheduler, ThreadScheduler, ProcessScheduler)):
        if isinstance(scheduler, AsyncScheduler):
            raise TypeError("use execute_workflow_async() with AsyncScheduler")
        if isinstance(scheduler, ProcessScheduler):
            run_task = functools.partial(
                _execute_process_task,
                policy=policy,
                workflow_id=workflow.id,
                workflow_execution_id=workflow_execution_id,
                provider_id=provider_id,
            )
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
                provider_id=provider_id,
                notify=notify,
            )
        results.update(
            scheduler.execute(
                workflow,
                run_task,
                on_start=lambda task_id: notify(EventType.TASK_STARTED, task_id),
                on_complete=lambda task_id, result: notify(
                    _task_terminal_event(result),
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
        if isinstance(scheduler, ProcessScheduler) and artifact_store is not None:
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
            provider_id=provider_id,
            notify=notify,
        )
        results[task.id] = result
        notify(
            _task_terminal_event(result),
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
    *,
    workflow_id: str,
    workflow_execution_id: str | None,
    provider_id: str | None = None,
) -> Result:
    """Process-safe callback; no live machine, observer, or cache crosses the boundary."""
    return _execute_task(
        task,
        LocalMachine(),
        dependency_results,
        policy,
        None,
        workflow_id=workflow_id,
        workflow_execution_id=workflow_execution_id,
        artifact_store=None,
        provider_id=provider_id,
    )


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
    provider_id = "local" if isinstance(machine, LocalMachine) else None

    def notify(
        event_type: EventType,
        task_id: str | None = None,
        result: Result | None = None,
        *,
        attempt_id: str | None = None,
        process_id: str | None = None,
        provider_id: str | None = provider_id,
        status: ProcessStatus | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        nonlocal sequence
        sequence += 1
        event = RuntimeEvent(
            sequence=sequence,
            event_type=event_type,
            workflow_id=workflow.id,
            task_id=task_id,
            execution_id=workflow_execution_id,
            attempt_id=attempt_id or (result.attempt_id if result is not None else None),
            provider_id=provider_id,
            process_id=process_id,
            status=status if status is not None else result.status if result is not None else None,
            metadata=(dict(result.metadata) | {"duration": result.duration} | dict(metadata or {})) if result is not None else dict(metadata or {}),
        )
        for observer in observers:
            emit_event(observer, event)

    async def run_task(task: Task, dependencies: Mapping[str, Result]) -> Result:
        operation = task.operation
        if callable(operation):
            attempt_id = f"{task.id}:1"
            notify(EventType.ATTEMPT_STARTED, task.id, attempt_id=attempt_id)
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
            result = replace(result, metadata={**result.metadata, "attempt_id": attempt_id})
            notify(EventType.ATTEMPT_COMPLETED, task.id, result, attempt_id=attempt_id)
            return _finalize_result(
                result,
                workflow_id=workflow.id,
                execution_id_value=workflow_execution_id,
                task_id=task.id,
                attempt_id=attempt_id,
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
            provider_id=provider_id,
            notify=notify,
        )

    notify(EventType.WORKFLOW_STARTED)
    if provider_id is not None:
        notify(EventType.PROVIDER_SELECTED, metadata={"provider": provider_id})
    results.update(await scheduler.execute(
        workflow,
        run_task,
        on_start=lambda task_id: notify(EventType.TASK_STARTED, task_id),
        on_complete=lambda task_id, result: notify(
            _task_terminal_event(result),
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
