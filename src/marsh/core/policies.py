"""Mechanism-independent execution policies and runtime-control decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from marsh.core.domain import ProcessStatus, Result
from marsh.core.cache import CachePolicy


class FailureClass(str, Enum):
    """Backend-independent failure classification used by retry policy."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TimeoutPolicy:
    """Provides a default timeout without overriding an explicit task timeout."""

    timeout: float

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")

    def resolve(self, explicit: float | None) -> float:
        return explicit if explicit is not None else self.timeout


@dataclass(frozen=True)
class RetryPolicy:
    """Controls bounded, conservative retries for failed attempts."""

    max_attempts: int = 1
    retryable_statuses: frozenset[ProcessStatus] = frozenset(
        {ProcessStatus.FAILED, ProcessStatus.TIMED_OUT}
    )
    retry_on: frozenset[FailureClass] = frozenset(
        {FailureClass.TRANSIENT, FailureClass.TIMEOUT}
    )
    backoff: float = 0.0
    allow_non_idempotent: bool = False

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff < 0:
            raise ValueError("backoff must be non-negative")

    def classify(self, result: Result) -> FailureClass:
        if result.status is ProcessStatus.TIMED_OUT:
            return FailureClass.TIMEOUT
        if result.status is ProcessStatus.CANCELLED:
            return FailureClass.CANCELLED
        if result.status is not ProcessStatus.FAILED:
            return FailureClass.UNKNOWN
        value = str(result.metadata.get("failure_class", FailureClass.TRANSIENT.value))
        try:
            return FailureClass(value)
        except ValueError:
            return FailureClass.UNKNOWN

    def should_retry(
        self,
        result: Result,
        attempt: int,
        *,
        idempotent: bool = True,
        cancellation_requested: bool = False,
        cleanup_succeeded: bool = True,
    ) -> bool:
        if attempt < 1:
            raise ValueError("attempt must be at least 1")
        if attempt >= self.max_attempts or cancellation_requested or not cleanup_succeeded:
            return False
        if not idempotent and not self.allow_non_idempotent:
            return False
        return (
            result.status in self.retryable_statuses
            and self.classify(result) in self.retry_on
        )


@dataclass(frozen=True)
class FailurePolicy:
    """Controls whether workflow execution continues after a failed task."""

    mode: str = "skip_dependents"

    def __post_init__(self) -> None:
        if self.mode not in {"skip_dependents", "fail_fast"}:
            raise ValueError("mode must be 'skip_dependents' or 'fail_fast'")

    def should_continue(self, result: Result) -> bool:
        return result.status not in {
            ProcessStatus.FAILED,
            ProcessStatus.TIMED_OUT,
        } or self.mode == "skip_dependents"


@dataclass(frozen=True)
class ResourcePolicy:
    """Describes provider resources available to a scheduling decision."""

    available: Mapping[str, Any]

    def supports(self, requested: Mapping[str, Any]) -> bool:
        for name, value in requested.items():
            if name not in self.available:
                return False
            available = self.available[name]
            if isinstance(value, (int, float)) and not isinstance(value, bool) and isinstance(available, (int, float)):
                if value > available:
                    return False
            elif value != available:
                return False
        return True


@dataclass(frozen=True)
class CleanupPolicy:
    """Controls cleanup failure behavior without rewriting the primary outcome."""

    enabled: bool = True
    block_retry_on_failure: bool = True


@dataclass(frozen=True)
class CancellationPolicy:
    """Controls whether cancellation is accepted as a terminal outcome."""

    enabled: bool = True
    retry_cancelled: bool = False


@dataclass(frozen=True)
class RestartPolicy:
    """Declarative restart intent; recovery mechanisms remain backend-owned."""

    enabled: bool = False
    max_restarts: int = 0


@dataclass(frozen=True)
class SchedulingPolicy:
    """Declarative scheduling metadata; scheduler semantics remain authoritative."""

    priority: int = 0
    fail_fast: bool = False


@dataclass(frozen=True)
class ExecutionPolicy:
    """Composable policy bundle applied by the workflow runtime."""

    retry: RetryPolicy = RetryPolicy()
    timeout: TimeoutPolicy | None = None
    resources: ResourcePolicy | None = None
    failure: FailurePolicy = FailurePolicy()
    cache: CachePolicy = CachePolicy()
    cleanup: CleanupPolicy = CleanupPolicy()
    cancellation: CancellationPolicy = CancellationPolicy()
    restart: RestartPolicy = RestartPolicy()
    scheduling: SchedulingPolicy = SchedulingPolicy()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "ExecutionPolicy":
        data = dict(value or {})
        unknown = set(data) - {
            "retry", "timeout", "resources", "failure", "cache",
            "cleanup", "cancellation", "restart", "scheduling",
        }
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown policy fields: {names}")

        retry_data = dict(data.get("retry") or {})
        retry = RetryPolicy(
            max_attempts=int(retry_data.get("max_attempts", 1)),
            backoff=float(retry_data.get("backoff", 0.0)),
            allow_non_idempotent=bool(retry_data.get("allow_non_idempotent", False)),
        )
        timeout_data = data.get("timeout")
        timeout = None if timeout_data is None else TimeoutPolicy(float(
            timeout_data.get("timeout") if isinstance(timeout_data, Mapping) else timeout_data
        ))
        resources_data = data.get("resources")
        resources = None if resources_data is None else ResourcePolicy(dict(resources_data.get("available", resources_data)))
        failure_data = data.get("failure")
        failure = FailurePolicy(str(failure_data.get("mode", "skip_dependents") if isinstance(failure_data, Mapping) else failure_data))
        cache_data = data.get("cache")
        cache = CachePolicy(
            enabled=bool(cache_data.get("enabled", False) if isinstance(cache_data, Mapping) else cache_data or False),
            namespace=str(cache_data.get("namespace", "marsh") if isinstance(cache_data, Mapping) else "marsh"),
        )
        cleanup_data = data.get("cleanup") or {}
        cancellation_data = data.get("cancellation") or {}
        restart_data = data.get("restart") or {}
        scheduling_data = data.get("scheduling") or {}
        return cls(
            retry=retry,
            timeout=timeout,
            resources=resources,
            failure=failure,
            cache=cache,
            cleanup=CleanupPolicy(
                enabled=bool(cleanup_data.get("enabled", True)),
                block_retry_on_failure=bool(cleanup_data.get("block_retry_on_failure", True)),
            ),
            cancellation=CancellationPolicy(
                enabled=bool(cancellation_data.get("enabled", True)),
                retry_cancelled=bool(cancellation_data.get("retry_cancelled", False)),
            ),
            restart=RestartPolicy(
                enabled=bool(restart_data.get("enabled", False)),
                max_restarts=int(restart_data.get("max_restarts", 0)),
            ),
            scheduling=SchedulingPolicy(
                priority=int(scheduling_data.get("priority", 0)),
                fail_fast=bool(scheduling_data.get("fail_fast", False)),
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "retry": {
                "max_attempts": self.retry.max_attempts,
                "backoff": self.retry.backoff,
                "allow_non_idempotent": self.retry.allow_non_idempotent,
            },
            "timeout": None if self.timeout is None else {"timeout": self.timeout.timeout},
            "resources": None if self.resources is None else {"available": dict(self.resources.available)},
            "failure": {"mode": self.failure.mode},
            "cache": {"enabled": self.cache.enabled, "namespace": self.cache.namespace},
            "cleanup": {
                "enabled": self.cleanup.enabled,
                "block_retry_on_failure": self.cleanup.block_retry_on_failure,
            },
            "cancellation": {
                "enabled": self.cancellation.enabled,
                "retry_cancelled": self.cancellation.retry_cancelled,
            },
            "restart": {
                "enabled": self.restart.enabled,
                "max_restarts": self.restart.max_restarts,
            },
            "scheduling": {
                "priority": self.scheduling.priority,
                "fail_fast": self.scheduling.fail_fast,
            },
        }


@dataclass(frozen=True)
class PolicyDecision:
    """Pure runtime-control decision derived from one attempt outcome."""

    status: ProcessStatus
    attempt: int
    retry: bool
    cleanup_required: bool
    cleanup_blocks_retry: bool
    failure_class: FailureClass
    reason: str


def evaluate_policy(
    policy: ExecutionPolicy,
    result: Result,
    *,
    attempt: int,
    idempotent: bool = True,
    cancellation_requested: bool = False,
    cleanup_succeeded: bool = True,
) -> PolicyDecision:
    """Resolve terminal outcome, cleanup, and retry in deterministic order."""
    if attempt < 1:
        raise ValueError("attempt must be at least 1")

    status = result.status
    failure_class = policy.retry.classify(result)
    cleanup_required = status in {
        ProcessStatus.COMPLETED,
        ProcessStatus.FAILED,
        ProcessStatus.TIMED_OUT,
        ProcessStatus.CANCELLED,
    }
    cleanup_blocks_retry = policy.cleanup.block_retry_on_failure and not cleanup_succeeded

    if cancellation_requested and status not in {
        ProcessStatus.CANCELLED,
        ProcessStatus.COMPLETED,
    }:
        return PolicyDecision(
            status=status,
            attempt=attempt,
            retry=False,
            cleanup_required=True,
            cleanup_blocks_retry=cleanup_blocks_retry,
            failure_class=failure_class,
            reason="cancellation requested; no new retry will be scheduled",
        )

    retry = policy.retry.should_retry(
        result,
        attempt,
        idempotent=idempotent,
        cancellation_requested=cancellation_requested,
        cleanup_succeeded=cleanup_succeeded,
    )
    if cleanup_blocks_retry:
        retry = False

    if status is ProcessStatus.CANCELLED:
        retry = policy.cancellation.retry_cancelled and retry
    if status is ProcessStatus.COMPLETED:
        retry = False

    return PolicyDecision(
        status=status,
        attempt=attempt,
        retry=retry,
        cleanup_required=cleanup_required,
        cleanup_blocks_retry=cleanup_blocks_retry,
        failure_class=failure_class,
        reason=(
            "retry eligible after successful cleanup"
            if retry
            else "terminal outcome accepted without retry"
        ),
    )
