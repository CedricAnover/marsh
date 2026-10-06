"""Bounded postcondition-based recovery primitives for Marsh."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Generic, TypeVar

T = TypeVar("T")

_DEFAULT_VERIFICATION_RETRIES = 8
_DEFAULT_VERIFICATION_RETRY_DELAY_SECONDS = 0.01
_DEFAULT_RETRYABLE_VERIFICATION_EXCEPTIONS = (PermissionError,)


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
    *,
    verification_retries: int = _DEFAULT_VERIFICATION_RETRIES,
    verification_retry_delay_seconds: float = _DEFAULT_VERIFICATION_RETRY_DELAY_SECONDS,
    retryable_verification_exceptions: tuple[
        type[Exception], ...
    ] = _DEFAULT_RETRYABLE_VERIFICATION_EXCEPTIONS,
) -> RecoveryResult[T]:
    """Execute once and resolve interrupted operations only by verified state.

    The operation is never retried blindly. If it raises, the independent
    verification query is authoritative. Verification may retry only narrowly
    classified transient exceptions, using a bounded linear delay. A verified
    postcondition resolves the operation; insufficient evidence remains
    explicitly ambiguous and retry exhaustion preserves the original failure.

    Args:
        operation: Operation whose result is returned when it succeeds.
        verify: Authoritative postcondition query used after an operation error.
        verification_retries: Maximum number of verification attempts.
        verification_retry_delay_seconds: Base delay between transient
            verification attempts; each retry waits one additional base unit.
        retryable_verification_exceptions: Exceptions considered transient at
            the verification boundary. By default this is ``PermissionError``.

    Raises:
        ValueError: If the verification retry budget or delay is invalid.
    """

    if verification_retries < 1:
        raise ValueError("verification_retries must be at least 1")
    if verification_retry_delay_seconds < 0:
        raise ValueError("verification_retry_delay_seconds must be non-negative")

    try:
        return RecoveryResult(RecoveryStatus.RESOLVED, value=operation())
    except Exception as exc:
        for attempt in range(verification_retries):
            try:
                verified = bool(verify())
            except retryable_verification_exceptions:
                if attempt == verification_retries - 1:
                    return RecoveryResult(RecoveryStatus.AMBIGUOUS, error=exc)
                time.sleep(verification_retry_delay_seconds * (attempt + 1))
                continue
            except Exception as verification_error:
                return RecoveryResult(
                    RecoveryStatus.AMBIGUOUS,
                    error=verification_error,
                )
            if verified:
                return RecoveryResult(RecoveryStatus.RESOLVED)
            return RecoveryResult(RecoveryStatus.AMBIGUOUS, error=exc)

    raise AssertionError("unreachable")


__all__ = ["RecoveryResult", "RecoveryStatus", "execute_with_postcondition"]
