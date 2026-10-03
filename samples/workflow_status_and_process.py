"""Inspect process lifecycle contracts and a real local process result."""

import sys

from marsh import LocalMachine, ProcessSpec, ProcessStatus


spec = ProcessSpec(
    executable=sys.executable,
    arguments=("-c", "print('status demo')"),
)

machine = LocalMachine()
process = machine.create_process(spec)

print("initial:", process.status.value)
process.start()
print("after start:", process.status.value)

result = process.wait()

assert result.status is ProcessStatus.COMPLETED
print("final:", result.status.value)
print("stdout:", result.stdout.decode().strip())
