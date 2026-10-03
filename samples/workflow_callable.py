"""Use a Python callable as a canonical task operation."""

from marsh import ProcessStatus, Result, Task, Workflow, execute_workflow


def calculate(inputs, dependencies):
    total = inputs["left"] + inputs["right"]
    return Result(
        stdout=str(total).encode(),
        status=ProcessStatus.COMPLETED,
        metadata={"operation": "addition"},
    )


workflow = Workflow(
    id="python-operation",
    tasks=(
        Task(
            id="sum",
            operation=calculate,
            inputs={"left": 7, "right": 5},
        ),
    ),
)

result = execute_workflow(workflow)["sum"]

if not result.ok:
    raise RuntimeError(result.error)

print("sum:", result.stdout.decode())
