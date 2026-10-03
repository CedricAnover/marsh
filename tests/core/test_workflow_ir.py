import json

import pytest

from marsh.core.configuration import TaskConfig, WorkflowConfig, normalize_workflow
from marsh.core.domain import Task, Workflow
from marsh.core.serialization import (
    workflow_from_json,
    workflow_to_dict,
    workflow_to_json,
    validate_workflow,
)


def test_python_and_dict_definitions_normalize_to_equivalent_ir():
    python_definition = Workflow(
        id="example",
        tasks=(
            Task(id="build", operation="echo", inputs={"value": "ok"}),
            Task(id="publish", operation="echo", dependencies=("build",)),
        ),
    )
    dict_definition = {
        "id": "example",
        "tasks": [
            {"id": "build", "operation": "echo", "inputs": {"value": "ok"}},
            {"id": "publish", "operation": "echo", "dependencies": ["build"]},
        ],
    }

    assert normalize_workflow(python_definition) == normalize_workflow(dict_definition)


def test_configuration_models_normalize_without_becoming_runtime_objects():
    config = WorkflowConfig.from_mapping(
        {
            "id": "example",
            "tasks": [
                {"id": "a", "operation": "echo", "outputs": ["message"]},
                {"id": "b", "operation": "echo", "dependencies": ["a"]},
            ],
        }
    )

    assert isinstance(config, WorkflowConfig)
    assert isinstance(config.tasks[0], TaskConfig)
    workflow = config.to_workflow()
    assert isinstance(workflow, Workflow)
    assert isinstance(workflow.tasks[0], Task)
    assert workflow.task("b").dependencies == ("a",)


def test_semantic_validation_rejects_dependency_cycles():
    workflow = Workflow(
        id="cyclic",
        tasks=(
            Task(id="a", operation="echo", dependencies=("b",)),
            Task(id="b", operation="echo", dependencies=("a",)),
        ),
    )

    with pytest.raises(ValueError, match="cycle"):
        validate_workflow(workflow)


def test_semantic_validation_returns_deterministic_topological_order():
    workflow = Workflow(
        id="ordered",
        tasks=(
            Task(id="c", operation="echo", dependencies=("a",)),
            Task(id="a", operation="echo"),
            Task(id="b", operation="echo"),
        ),
    )

    assert validate_workflow(workflow) == ("a", "b", "c")


def test_serialization_is_deterministic_and_round_trips():
    workflow = Workflow(
        id="example",
        tasks=(
            Task(
                id="run",
                operation="echo",
                inputs={"z": 2, "a": 1},
                metadata={"b": "two", "a": "one"},
            ),
        ),
        inputs={"z": 2, "a": 1},
        metadata={"z": "last", "a": "first"},
    )

    first = workflow_to_json(workflow)
    second = workflow_to_json(workflow)

    assert first == second
    assert json.loads(first) == workflow_to_dict(workflow)
    assert workflow_from_json(first) == workflow


def test_serialization_rejects_non_data_operations():
    workflow = Workflow(id="callable", tasks=(Task(id="run", operation=lambda: None),))

    with pytest.raises(TypeError, match="serializable"):
        workflow_to_json(workflow)
