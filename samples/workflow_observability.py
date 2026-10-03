"""Observe runtime lifecycle events without affecting execution."""

import sys

from marsh import ProcessSpec, Task, Workflow, execute_workflow


class Printer:
    def on_event(self, event):
        print(
            event.sequence,
            event.event_type.value,
            event.task_id or "<workflow>",
            event.status.value if event.status else "",
        )


workflow = Workflow(
    id="events",
    tasks=(
        Task(
            id="hello",
            operation=ProcessSpec(
                executable=sys.executable,
                arguments=("-c", "print('observed')"),
            ),
        ),
    ),
)

results = execute_workflow(workflow, observers=(Printer(),))
assert results["hello"].status.value == "completed"
