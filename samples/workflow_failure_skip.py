"""Show how a failed dependency causes downstream work to be skipped."""

from marsh import ProcessStatus, Result, Task, Workflow, execute_workflow


def fail(_, __):
    return Result(
        status=ProcessStatus.FAILED,
        error="intentional example failure",
    )


def should_not_run(_, __):
    raise AssertionError("skipped task was executed")


workflow = Workflow(
    id="failure-skip",
    tasks=(
        Task(id="fail", operation=fail),
        Task(
            id="downstream",
            operation=should_not_run,
            dependencies=("fail",),
        ),
    ),
)

results = execute_workflow(workflow)

print("failed:", results["fail"].status.value)
print("downstream:", results["downstream"].status.value)
assert results["downstream"].status is ProcessStatus.SKIPPED
