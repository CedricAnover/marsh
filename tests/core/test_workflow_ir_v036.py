import json
import subprocess
import sys

import pytest

from marsh.core.domain import ProcessSpec, Task, Workflow
from marsh.core.ir.errors import OperationResolutionError, SerializationError, UnsupportedSchemaVersionError
from marsh.core.ir.operations import operation_to_ref, resolve_operation
from marsh.core.serialization import workflow_from_json, workflow_to_dict, workflow_to_json, workflow_to_document


def top_level_operation(inputs, dependencies):
    from marsh.core.domain import Result
    return Result(stdout=b"ok")


def test_document_has_independent_schema_version_and_stable_identity():
    workflow = Workflow(
        id="workflow-1",
        tasks=(Task(id="task-1", operation="echo"),),
    )
    document = workflow_to_document(workflow)
    assert document.schema == {"name": "marsh.workflow", "version": 1}
    assert document.workflow["id"] == "workflow-1"
    assert document.workflow["tasks"][0]["id"] == "task-1"


def test_canonical_json_is_independent_of_task_and_mapping_insertion_order():
    first = Workflow(
        id="stable",
        tasks=(
            Task(id="b", operation="echo", inputs={"z": 2, "a": 1}),
            Task(id="a", operation="echo", inputs={"b": 2, "a": 1}),
        ),
    )
    second = Workflow(
        id="stable",
        tasks=(
            Task(id="a", operation="echo", inputs={"a": 1, "b": 2}),
            Task(id="b", operation="echo", inputs={"a": 1, "z": 2}),
        ),
    )
    assert workflow_to_json(first) == workflow_to_json(second)


def test_importable_callable_is_explicitly_referenced_and_reconstructed():
    workflow = Workflow(id="callable", tasks=(Task(id="run", operation=top_level_operation),))
    data = workflow_to_dict(workflow)
    operation = data["workflow"]["tasks"][0]["operation"]
    assert operation == {
        "kind": "python_callable",
        "module": __name__,
        "qualname": "top_level_operation",
    }
    restored = workflow_from_json(workflow_to_json(workflow))
    assert restored.task("run").operation is top_level_operation


def test_local_and_lambda_callables_are_rejected():
    local = lambda: None
    with pytest.raises((OperationResolutionError, SerializationError, TypeError)):
        workflow_to_json(Workflow(id="x", tasks=(Task(id="t", operation=local),)))


def test_non_finite_and_unsupported_values_are_rejected():
    with pytest.raises(SerializationError, match="non-finite"):
        workflow_to_json(Workflow(id="x", tasks=(Task(id="t", operation="echo", inputs={"x": float("nan")}),)))
    with pytest.raises(SerializationError, match="bytes"):
        workflow_to_json(Workflow(id="x", tasks=(Task(id="t", operation="echo", inputs={"x": b"x"}),)))


def test_unknown_schema_version_is_rejected():
    data = workflow_to_dict(Workflow(id="x", tasks=(Task(id="t", operation="echo"),)))
    data["schema"]["version"] = 99
    with pytest.raises(UnsupportedSchemaVersionError):
        workflow_from_json(json.dumps(data))


def test_process_spec_round_trip_preserves_semantics():
    spec = ProcessSpec(
        executable=sys.executable,
        arguments=("-c", "print('ok')"),
        environment={"MODE": "test"},
        working_directory=None,
        timeout=5,
    )
    restored = workflow_from_json(workflow_to_json(
        Workflow(id="process", tasks=(Task(id="run", operation=spec),))
    ))
    assert restored.task("run").operation == spec


def test_resolution_does_not_evaluate_serialized_code():
    ref = operation_to_ref(top_level_operation)
    assert resolve_operation(ref) is top_level_operation
