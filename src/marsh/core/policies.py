"""Mechanism-independent execution policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from marsh.core.domain import ProcessStatus, Result


@dataclass(frozen=True)
class RetryPolicy:
    """Controls whether a failed attempt may be retried."""

    max_attempts: int = 1

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

    def should_retry(self, result: Result, attempt: int) -> bool:
        if attempt < 1:
            raise ValueError("attempt must be at least 1")
        return (
            result.status in {ProcessStatus.FAILED, ProcessStatus.TIMED_OUT}
            and attempt < self.max_attempts
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
            if isinstance(value, (int, float)) and isinstance(available, (int, float)):
                if value > available:
                    return False
            elif value != available:
                return False
        return True
