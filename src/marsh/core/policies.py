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
