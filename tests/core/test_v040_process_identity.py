import sys

from marsh.core.runtime import LocalMachine
from marsh.core.domain import ProcessSpec


def test_process_identity_is_stable_and_not_a_pid():
    process = LocalMachine().create_process(ProcessSpec(executable=sys.executable))

    assert process.process_id
    assert process.process_id == process.process_id
    assert process.process_id != str(getattr(process, "_process", None))
