from dataclasses import dataclass
from pathlib import Path

import pytest

from marsh.core.domain import ProcessSpec, Task, Workflow
from marsh.core.identity import canonical_bytes, execution_id, content_digest


def test_canonical_bytes_are_stable_across_mapping_insertion_order():
    first = Workflow(
        id="example",
        inputs={"z": 2, "a": 1},
        tasks=(Task(id="run", operation=ProcessSpec("echo", ("ok",))),),
    )
    second = Workflow(
        id="example",
        inputs={"a": 1, "z": 2},
        tasks=(Task(id="run", operation=ProcessSpec("echo", ("ok",))),),
    )

    assert canonical_bytes(first) == canonical_bytes(second)
    assert execution_id(first) == execution_id(second)


def test_execution_identity_excludes_nonsemantic_working_directory():
    first = Workflow(
        id="paths",
        tasks=(
            Task(
                id="run",
                operation=ProcessSpec("echo", ("ok",), working_directory="/tmp/one"),
            ),
        ),
    )
    second = Workflow(
        id="paths",
        tasks=(
            Task(
                id="run",
                operation=ProcessSpec("echo", ("ok",), working_directory="/tmp/two"),
            ),
        ),
    )

    assert execution_id(first) == execution_id(second)


def test_execution_identity_changes_for_semantic_inputs():
    first = Workflow(
        id="inputs",
        inputs={"value": "one"},
        tasks=(Task(id="run", operation=ProcessSpec("echo", ("ok",))),),
    )
    second = Workflow(
        id="inputs",
        inputs={"value": "two"},
        tasks=(Task(id="run", operation=ProcessSpec("echo", ("ok",))),),
    )

    assert execution_id(first) != execution_id(second)


def test_content_digest_is_independent_of_storage_location():
    assert content_digest(b"same bytes") == content_digest(b"same bytes")


def test_non_finite_identity_values_are_rejected():
    workflow = Workflow(
        id="invalid",
        inputs={"value": float("nan")},
        tasks=(Task(id="run", operation=ProcessSpec("echo", ("ok",))),),
    )

    with pytest.raises(ValueError, match="finite|unsupported"):
        canonical_bytes(workflow)


def test_runtime_objects_are_not_serialized_as_identity_data():
    @dataclass
    class RuntimeOnly:
        value: str

    workflow = Workflow(
        id="runtime-only",
        inputs={"runtime": RuntimeOnly("secret")},
        tasks=(Task(id="run", operation=ProcessSpec("echo", ("ok",))),),
    )

    with pytest.raises(TypeError, match="unsupported"):
        canonical_bytes(workflow)
