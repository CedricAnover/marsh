import pytest

from marsh.core.configuration import WorkflowConfig
from marsh.core.domain import Task, Workflow


def test_workflow_config_rejects_unknown_fields():
    with pytest.raises(ValueError, match="unknown fields: mystery"):
        WorkflowConfig.from_mapping(
            {
                "id": "wf",
                "tasks": [],
                "mystery": True,
            }
        )


def test_workflow_config_rejects_blank_task_id():
    with pytest.raises(ValueError, match="task id must be non-empty"):
        WorkflowConfig.from_mapping(
            {
                "id": "wf",
                "tasks": [{"id": " ", "operation": lambda i, d: None}],
            }
        )


def test_validate_workflow_reports_duplicate_outputs_and_unknown_dependencies():
    from marsh.core.validation import validate_workflow

    diagnostics = validate_workflow(
        {
            "id": "wf",
            "tasks": [
                {"id": "a", "operation": lambda i, d: None, "outputs": ["x"]},
                {
                    "id": "b",
                    "operation": lambda i, d: None,
                    "outputs": ["x"],
                    "dependencies": ["missing"],
                },
            ],
        }
    )

    assert [item.code for item in diagnostics] == [
        "DUPLICATE_OUTPUT",
        "UNKNOWN_DEPENDENCY",
    ]
    assert all(item.severity == "error" for item in diagnostics)


def test_validate_workflow_reports_cycles_deterministically():
    from marsh.core.validation import validate_workflow

    workflow = Workflow(
        id="wf",
        tasks=(
            Task(id="a", operation=lambda i, d: None, dependencies=("b",)),
            Task(id="b", operation=lambda i, d: None, dependencies=("a",)),
        ),
    )

    diagnostics = validate_workflow(workflow)

    assert [(item.code, item.message) for item in diagnostics] == [
        ("DEPENDENCY_CYCLE", "workflow contains a dependency cycle")
    ]
