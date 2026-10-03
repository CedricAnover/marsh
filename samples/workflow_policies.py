"""Combine timeout, resource, retry, failure, and cache policy settings."""

import sys

from marsh import (
    CachePolicy,
    ExecutionPolicy,
    FailurePolicy,
    ProcessSpec,
    ResourcePolicy,
    RetryPolicy,
    Task,
    TimeoutPolicy,
    Workflow,
    execute_workflow,
)


workflow = Workflow(
    id="policy-demo",
    tasks=(
        Task(
            id="job",
            operation=ProcessSpec(
                executable=sys.executable,
                arguments=("-c", "print('policy controlled')"),
            ),
            metadata={"resources": {"cpu": 1}},
        ),
    ),
)

policy = ExecutionPolicy(
    retry=RetryPolicy(max_attempts=2),
    timeout=TimeoutPolicy(timeout=5),
    resources=ResourcePolicy(available={"cpu": 2}),
    failure=FailurePolicy(mode="skip_dependents"),
    cache=CachePolicy(enabled=False),
)

result = execute_workflow(workflow, policy=policy)["job"]

if not result.ok:
    raise RuntimeError(result.error)

print(result.stdout.decode().strip())
