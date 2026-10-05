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
