"""Smallest useful canonical Workflow API example."""

import sys

from marsh import ProcessSpec, Task, Workflow, execute_workflow


workflow = Workflow(
    id="hello",
    tasks=(
        Task(
            id="greet",
            operation=ProcessSpec(
                executable=sys.executable,
                arguments=("-c", "print('hello from Marsh')"),
            ),
        ),
    ),
)

results = execute_workflow(workflow)
result = results["greet"]

if not result.ok:
    raise RuntimeError(result.error)

print(result.stdout.decode().strip())
