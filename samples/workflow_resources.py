"""Check requested task resources against a provider resource policy."""

import sys

from marsh import (
    ExecutionPolicy,
    ProcessSpec,
    ResourcePolicy,
    Task,
    Workflow,
    execute_workflow,
)


workflow = Workflow(
    id="resources",
    tasks=(
        Task(
            id="job",
            operation=ProcessSpec(
                executable=sys.executable,
                arguments=("-c", "print('resources available')"),
            ),
            metadata={"resources": {"cpu": 1, "memory": 256}},
        ),
    ),
)

policy = ExecutionPolicy(
    resources=ResourcePolicy(
        available={"cpu": 2, "memory": 1024},
    )
)

result = execute_workflow(workflow, policy=policy)["job"]

if not result.ok:
    raise RuntimeError(result.error)

print(result.stdout.decode().strip())
