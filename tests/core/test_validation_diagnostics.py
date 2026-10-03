import pytest

from marsh.core.configuration import WorkflowConfig, normalize_workflow
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

    workflow = object.__new__(Workflow)
    object.__setattr__(workflow, "id", "wf")
    task = Task(id="a", operation=lambda i, d: None, outputs=("x",))
    task2 = Task(id="b", operation=lambda i, d: None, outputs=("x",), dependencies=("missing",))
    object.__setattr__(workflow, "tasks", (task, task2))
    object.__setattr__(workflow, "inputs", {})
    object.__setattr__(workflow, "outputs", {})
    object.__setattr__(workflow, "metadata", {})

    diagnostics = validate_workflow(workflow)

    assert [item.code for item in diagnostics] == ["DUPLICATE_OUTPUT", "UNKNOWN_DEPENDENCY"]
    assert all(item.severity == "error" for item in diagnostics)


def test_validate_workflow_reports_cycles_deterministically():
    from marsh.core.validation import validate_workflow

    workflow = object.__new__(Workflow)
    object.__setattr__(workflow, "id", "wf")
    a = Task(id="a", operation=lambda i, d: None, dependencies=("b",))
    b = Task(id="b", operation=lambda i, d: None, dependencies=("a",))
    object.__setattr__(workflow, "tasks", (a, b))
    object.__setattr__(workflow, "inputs", {})
    object.__setattr__(workflow, "outputs", {})
    object.__setattr__(workflow, "metadata", {})

    diagnostics = validate_workflow(workflow)

    assert [(item.code, item.message) for item in diagnostics] == [
        ("DEPENDENCY_CYCLE", "workflow contains a dependency cycle")
    ]
