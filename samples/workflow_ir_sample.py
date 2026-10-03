"""End-to-end example using Marsh's canonical Python workflow API.

Run from a source checkout with:
    python samples/workflow_ir_sample.py
"""

import sys

from marsh import (
    ProcessSpec,
    Workflow,
    Task,
    execute_workflow,
    plan_workflow,
    validate_workflow,
)


def main() -> None:
    workflow = Workflow(
        id="example",
        tasks=(
            Task(
                id="greet",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "print('hello from Marsh')"),
                ),
            ),
        ),
    )

    order = validate_workflow(workflow)
    plan = plan_workflow(workflow)
    print(f"workflow: {workflow.id}")
    print(f"task order: {', '.join(order)}")
    print(f"initially ready: {', '.join(plan.ready)}")

    results = execute_workflow(workflow)
    for task_id, result in results.items():
        print(f"task: {task_id}")
        print(result.stdout.decode().strip())
        if not result.ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
