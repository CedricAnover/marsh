import time

from marsh.core.recovery import RecoveryStatus, execute_with_postcondition


def test_recovery_resolves_from_verified_postcondition():
    called = []

    def operation():
        called.append("operation")
        raise PermissionError("already materialized")

    def verify():
        called.append("verify")
        return True

    result = execute_with_postcondition(operation, verify)

    assert result.status is RecoveryStatus.RESOLVED
    assert result.resolved is True
    assert result.error is None
    assert called == ["operation", "verify"]


def test_recovery_preserves_ambiguity_when_postcondition_is_not_proven():
    def operation():
        raise TimeoutError("transport interrupted")

    result = execute_with_postcondition(operation, lambda: False)

    assert result.status is RecoveryStatus.AMBIGUOUS
    assert result.resolved is False
    assert isinstance(result.error, TimeoutError)


def test_recovery_does_not_turn_verification_failure_into_success():
    def operation():
        raise RuntimeError("operation interrupted")

    def verify():
        raise OSError("verification unavailable")

    result = execute_with_postcondition(operation, verify)

    assert result.status is RecoveryStatus.AMBIGUOUS
    assert isinstance(result.error, OSError)


def test_recovery_retries_transient_verification_failure_until_postcondition_is_proven(
    monkeypatch,
):
    verification_attempts = []
    sleeps = []

    def operation():
        raise PermissionError("operation interrupted during finalization")

    def verify():
        verification_attempts.append(len(verification_attempts) + 1)
        if len(verification_attempts) < 3:
            raise PermissionError("verification temporarily unavailable")
        return True

    monkeypatch.setattr(time, "sleep", sleeps.append)

    result = execute_with_postcondition(operation, verify)

    assert result.status is RecoveryStatus.RESOLVED
    assert result.error is None
    assert verification_attempts == [1, 2, 3]
    assert len(sleeps) == 2
    assert sleeps[0] < sleeps[1]


def test_recovery_preserves_operation_failure_after_transient_verification_exhaustion(
    monkeypatch,
):
    verification_attempts = []
    operation_error = PermissionError("operation interrupted during finalization")

    def operation():
        raise operation_error

    def verify():
        verification_attempts.append(1)
        raise PermissionError("verification remains temporarily unavailable")

    monkeypatch.setattr(time, "sleep", lambda _: None)

    result = execute_with_postcondition(operation, verify, verification_retries=4)

    assert result.status is RecoveryStatus.AMBIGUOUS
    assert result.resolved is False
    assert result.error is operation_error
    assert len(verification_attempts) == 4


def test_recovery_does_not_retry_non_transient_verification_failure(monkeypatch):
    verification_attempts = []
    sleeps = []
    verification_error = OSError("verification unavailable")

    def operation():
        raise RuntimeError("operation interrupted")

    def verify():
        verification_attempts.append(1)
        raise verification_error

    monkeypatch.setattr(time, "sleep", sleeps.append)

    result = execute_with_postcondition(operation, verify)

    assert result.status is RecoveryStatus.AMBIGUOUS
    assert result.error is verification_error
    assert verification_attempts == [1]
    assert sleeps == []


def test_provider_partial_failure_restores_state_only_after_verified_postcondition():
    state = {"resource": "allocated"}
    cleanup_calls = []

    def operation():
        raise RuntimeError("provider failed after allocation")

    def restore():
        cleanup_calls.append(1)
        state["resource"] = "released"

    def verify():
        return state["resource"] == "released"

    restore()
    result = execute_with_postcondition(operation, verify)

    assert result.status is RecoveryStatus.RESOLVED
    assert state["resource"] == "released"
    assert cleanup_calls == [1]

    # Reconciliation is idempotent when the desired postcondition already holds.
    restore()
    assert state["resource"] == "released"
    assert cleanup_calls == [1, 1]


def test_provider_partial_failure_stays_ambiguous_when_restoration_cannot_be_verified():
    state = {"resource": "unknown"}

    def operation():
        raise RuntimeError("provider failed after side effect")

    result = execute_with_postcondition(
        operation,
        lambda: state["resource"] == "released",
    )

    assert result.status is RecoveryStatus.AMBIGUOUS
    assert state["resource"] == "unknown"


def test_provider_partial_failure_recovery_models_adapter_owned_restoration():
    state = {"resource": "absent"}
    cleanup_calls = []

    def operation():
        state["resource"] = "allocated"
        try:
            raise RuntimeError("provider failed after allocation")
        except RuntimeError:
            cleanup_calls.append(1)
            state["resource"] = "released"
            raise

    result = execute_with_postcondition(
        operation,
        lambda: state["resource"] == "released",
    )

    assert result.status is RecoveryStatus.RESOLVED
    assert state["resource"] == "released"
    assert cleanup_calls == [1]


def test_provider_partial_failure_recovery_preserves_ambiguity_when_state_is_unknown():
    state = {"resource": "unknown"}

    def operation():
        state["resource"] = "unknown"
        raise RuntimeError("provider failed after side effect")

    result = execute_with_postcondition(
        operation,
        lambda: state["resource"] == "released",
    )

    assert result.status is RecoveryStatus.AMBIGUOUS
    assert state["resource"] == "unknown"
