"""Read dependency results explicitly from a callable task."""

from marsh import ProcessStatus, Result, Task, Workflow, execute_workflow


def produce(_, __):
    return Result(
        stdout=b"marsh",
        status=ProcessStatus.COMPLETED,
    )


def consume(_, dependencies):
    value = dependencies["produce"].stdout.decode().upper()
    return Result(
        stdout=value.encode(),
        status=ProcessStatus.COMPLETED,
    )


workflow = Workflow(
    id="dependency-data",
    tasks=(
        Task(id="produce", operation=produce),
        Task(
            id="consume",
            operation=consume,
            dependencies=("produce",),
        ),
    ),
)

result = execute_workflow(workflow)["consume"]

if not result.ok:
    raise RuntimeError(result.error)

print("dependency value:", result.stdout.decode())
