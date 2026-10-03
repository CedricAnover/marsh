"""Apply a default timeout policy to a task without an explicit timeout."""

import sys

from marsh import ExecutionPolicy, ProcessStatus, ProcessSpec, Task, TimeoutPolicy, Workflow, execute_workflow


workflow = Workflow(
    id="timeout",
    tasks=(
        Task(
            id="slow",
            operation=ProcessSpec(
                executable=sys.executable,
                arguments=("-c", "import time; time.sleep(0.2)"),
            ),
        ),
    ),
)

policy = ExecutionPolicy(timeout=TimeoutPolicy(timeout=0.05))
result = execute_workflow(workflow, policy=policy)["slow"]

assert result.status is ProcessStatus.TIMED_OUT
print("status:", result.status.value)
