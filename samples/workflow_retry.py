"""Retry a callable operation after a failed attempt."""

from marsh import (
    ExecutionPolicy,
    ProcessStatus,
    Result,
    RetryPolicy,
    Task,
    Workflow,
    execute_workflow,
)


attempts = 0


def flaky(_, __):
    global attempts
    attempts += 1
    if attempts == 1:
        return Result(
            status=ProcessStatus.FAILED,
            error="simulated transient failure",
        )
    return Result(
        stdout=b"recovered",
        status=ProcessStatus.COMPLETED,
    )


workflow = Workflow(
    id="retry-demo",
    tasks=(Task(id="flaky", operation=flaky),),
)

policy = ExecutionPolicy(retry=RetryPolicy(max_attempts=2))
result = execute_workflow(workflow, policy=policy)["flaky"]

if not result.ok:
    raise RuntimeError(result.error)

print("attempts:", attempts)
print("result:", result.stdout.decode())
