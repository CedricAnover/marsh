import sys

from marsh.core.domain import ProcessSpec, ProcessStatus
from marsh.core.runtime import LocalMachine


def test_local_process_timeout_is_distinct_from_failure():
    process = LocalMachine().create_process(
        ProcessSpec(
            executable=sys.executable,
            arguments=("-c", "import time; time.sleep(1)"),
            timeout=0.01,
        )
    )

    process.start()
    result = process.wait()

    assert result.status is ProcessStatus.TIMED_OUT
    assert result.failed is True
    assert result.metadata["timeout"] is True
    assert result.metadata["cancellation"] == "not_requested"


def test_local_process_cancellation_is_confirmed_after_wait():
    process = LocalMachine().create_process(
        ProcessSpec(
            executable=sys.executable,
            arguments=("-c", "import time; time.sleep(1)"),
        )
    )

    process.start()
    process.cancel()
    result = process.wait()

    assert result.status is ProcessStatus.CANCELLED
    assert result.failed is False
    assert result.metadata["cancellation"] == "confirmed"
