import pytest

from marsh.core.domain import ProcessStatus, can_transition, is_terminal


def test_v040_terminal_outcomes_are_explicit_and_non_regressing():
    terminal = {
        ProcessStatus.COMPLETED,
        ProcessStatus.FAILED,
        ProcessStatus.CANCELLED,
        ProcessStatus.TIMED_OUT,
        ProcessStatus.SKIPPED,
    }

    assert {status for status in ProcessStatus if is_terminal(status)} == terminal

    for status in terminal:
        assert not can_transition(status, ProcessStatus.RUNNING)


def test_v040_active_lifecycle_has_no_unlisted_transition():
    active = (
        ProcessStatus.CREATED,
        ProcessStatus.STARTING,
        ProcessStatus.RUNNING,
        ProcessStatus.STOPPING,
    )

    allowed = {
        (ProcessStatus.CREATED, ProcessStatus.STARTING),
        (ProcessStatus.CREATED, ProcessStatus.CANCELLED),
        (ProcessStatus.STARTING, ProcessStatus.RUNNING),
        (ProcessStatus.STARTING, ProcessStatus.FAILED),
        (ProcessStatus.STARTING, ProcessStatus.CANCELLED),
        (ProcessStatus.RUNNING, ProcessStatus.STOPPING),
        (ProcessStatus.RUNNING, ProcessStatus.COMPLETED),
        (ProcessStatus.RUNNING, ProcessStatus.FAILED),
        (ProcessStatus.RUNNING, ProcessStatus.CANCELLED),
        (ProcessStatus.RUNNING, ProcessStatus.TIMED_OUT),
        (ProcessStatus.STOPPING, ProcessStatus.COMPLETED),
        (ProcessStatus.STOPPING, ProcessStatus.FAILED),
        (ProcessStatus.STOPPING, ProcessStatus.CANCELLED),
    }

    for current in active:
        for target in active:
            assert (current, target) in allowed or not can_transition(current, target)


def test_v040_invalid_status_value_is_rejected():
    with pytest.raises(ValueError):
        ProcessStatus("unknown")
