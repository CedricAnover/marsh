"""Author a workflow with WorkflowConfig and normalize it into the IR."""

from marsh import ProcessSpec, TaskConfig, WorkflowConfig


config = WorkflowConfig(
    id="configured",
    tasks=(
        TaskConfig(
            id="hello",
            operation=ProcessSpec("python", ("-c", "print('configured')")),
            inputs={"source": "config"},
        ),
    ),
    metadata={"authoring": "WorkflowConfig"},
)

workflow = config.to_workflow()
print("workflow:", workflow.id)
print("task:", workflow.tasks[0].id)
print("input:", workflow.tasks[0].inputs["source"])
