import pytest

from marsh.core.configuration import WorkflowConfig
from marsh.core.domain import Task, Workflow


def test_workflow_config_rejects_unknown_fields():
    with pytest.raises(ValueError, match="unknown fields: mystery"):
        WorkflowConfig.from_mapping({"id": "wf", "tasks": [], "mystery": True})


def test_workflow_config_rejects_blank_task_id():
    with pytest.raises(ValueError, match="task id must be non-empty"):
        WorkflowConfig.from_mapping(
            {"id": "wf", "tasks": [{"id": " ", "operation": lambda i, d: None}]}
        )


def test_validate_workflow_reports_duplicate_outputs():
    from marsh.core.validation import validate_workflow_diagnostics

    workflow = Workflow(
        id="wf",
        tasks=(
            Task(id="a", operation=lambda i, d: None, outputs=("x",)),
            Task(id="b", operation=lambda i, d: None, outputs=("x",)),
        ),
    )

    diagnostics = validate_workflow_diagnostics(workflow)

    assert [(item.code, item.task_id) for item in diagnostics] == [
        ("DUPLICATE_OUTPUT", "b")
    ]


def test_validate_workflow_reports_unknown_dependencies():
    from marsh.core.validation import validate_workflow_diagnostics

    diagnostics = validate_workflow_diagnostics(
        {
            "id": "wf",
            "tasks": [
                {"id": "a", "operation": lambda i, d: None},
                {
                    "id": "b",
                    "operation": lambda i, d: None,
                    "dependencies": ["missing"],
                },
            ],
        }
    )

    assert [(item.code, item.message) for item in diagnostics] == [
        ("UNKNOWN_DEPENDENCY", "task 'b' has unknown dependencies: missing")
    ]


def test_validate_workflow_reports_cycles_deterministically():
    from marsh.core.validation import validate_workflow_diagnostics

    workflow = Workflow(
        id="wf",
        tasks=(
            Task(id="a", operation=lambda i, d: None, dependencies=("b",)),
            Task(id="b", operation=lambda i, d: None, dependencies=("a",)),
        ),
    )

    diagnostics = validate_workflow_diagnostics(workflow)

    assert [(item.code, item.message) for item in diagnostics] == [
        ("DEPENDENCY_CYCLE", "workflow contains a dependency cycle")
    ]
