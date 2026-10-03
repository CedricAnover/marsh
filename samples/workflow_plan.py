"""Validate a workflow and inspect its deterministic execution plan."""

from marsh import ProcessSpec, Task, Workflow, plan_workflow, validate_workflow


workflow = Workflow(
    id="build-test",
    tasks=(
        Task(
            id="test",
            operation=ProcessSpec("python", ("-c", "print('test')")),
            dependencies=("build",),
        ),
        Task(
            id="build",
            operation=ProcessSpec("python", ("-c", "print('build')")),
        ),
    ),
)

print("validated order:", validate_workflow(workflow))

plan = plan_workflow(workflow)
print("plan order:", plan.order)
print("initially ready:", plan.ready)
