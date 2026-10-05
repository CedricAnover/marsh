import sys

from marsh.core.domain import ProcessSpec
from marsh.core.runtime import LocalMachine


def test_process_identity_is_stable_across_lifecycle():
    process = LocalMachine().create_process(
        ProcessSpec(executable=sys.executable, arguments=("-c", "print('ok')"))
    )
    identity = process.process_id

    process.start()
    result = process.wait()

    assert identity
    assert process.process_id == identity
    assert result.stdout.strip() == b"ok"
