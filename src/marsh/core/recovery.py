"""Bounded postcondition-based recovery primitives for Marsh."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


class RecoveryStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class RecoveryResult(Generic[T]):
    """Outcome of an operation plus independent postcondition verification."""

    status: RecoveryStatus
    value: T | None = None
    error: Exception | None = None

    @property
    def resolved(self) -> bool:
        return self.status is RecoveryStatus.RESOLVED


def execute_with_postcondition(
    operation: Callable[[], T],
    verify: Callable[[], bool],
) -> RecoveryResult[T]:
    """Execute once and resolve interrupted operations only by verified state.

    The operation is never retried blindly. If it raises, the independent
    verification query is authoritative: a verified postcondition resolves the
    operation; insufficient evidence remains explicitly ambiguous.
    """

    try:
        return RecoveryResult(RecoveryStatus.RESOLVED, value=operation())
    except Exception as exc:
        try:
            verified = bool(verify())
        except Exception as verification_error:
            return RecoveryResult(
                RecoveryStatus.AMBIGUOUS,
                error=verification_error,
            )
        if verified:
            return RecoveryResult(RecoveryStatus.RESOLVED)
        return RecoveryResult(RecoveryStatus.AMBIGUOUS, error=exc)


__all__ = ["RecoveryResult", "RecoveryStatus", "execute_with_postcondition"]
