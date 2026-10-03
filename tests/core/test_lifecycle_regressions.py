import sys

import pytest

from marsh.core.domain import ProcessStatus, ProcessSpec
from marsh.core.runtime import LocalMachine


def test_local_process_cancel_before_start_is_terminal():
    process = LocalMachine().create_process(
        ProcessSpec(executable=sys.executable, arguments=("-c", "print('unused')"))
    )

    process.cancel()

    assert process.status is ProcessStatus.CANCELLED
    assert process.wait().status is ProcessStatus.CANCELLED

    with pytest.raises(RuntimeError, match="cannot start"):
        process.start()


def test_local_process_cannot_restart_after_completion():
    process = LocalMachine().create_process(
        ProcessSpec(executable=sys.executable, arguments=("-c", "print('ok')"))
    )

    process.start()
    assert process.wait().status is ProcessStatus.COMPLETED

    with pytest.raises(RuntimeError, match="cannot start"):
        process.start()
