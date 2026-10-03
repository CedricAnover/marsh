"""Stop scheduling after a failure when fail_fast is selected."""

from marsh import ExecutionPolicy, FailurePolicy, ProcessStatus, Result, Task, Workflow, execute_workflow


def fail(_, __):
    return Result(status=ProcessStatus.FAILED, error="stop here")


workflow = Workflow(
    id="fail-fast",
    tasks=(
        Task(id="first", operation=fail),
        Task(id="later", operation=lambda *_: Result(stdout=b"ran", status=ProcessStatus.COMPLETED)),
    ),
)

policy = ExecutionPolicy(failure=FailurePolicy(mode="fail_fast"))
results = execute_workflow(workflow, policy=policy)

assert results["first"].status is ProcessStatus.FAILED
assert "later" not in results
print("failed task:", results["first"].status.value)
print("later scheduled:", "later" in results)
