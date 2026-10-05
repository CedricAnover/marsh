import json

from marsh import ProcessSpec, Task, Workflow, inspect_workflow
from marsh.cli import EXIT_SUCCESS, main


def _workflow():
    return Workflow(
        id="inspect",
        tasks=(
            Task(
                id="b",
                operation=ProcessSpec(executable="python"),
                dependencies=("a",),
            ),
            Task(id="a", operation=ProcessSpec(executable="python")),
        ),
    )


def test_semantic_inspection_is_read_only_and_deterministic():
    workflow = _workflow()

    first = inspect_workflow(workflow)
    second = inspect_workflow(workflow)

    assert first == second
    assert first["plan"]["order"] == ["a", "b"]
    assert first["execution"]["performed"] is False
    assert first["lifecycle"]["status"] == "not_started"
    assert first["process"]["identity"] is None
    assert first["artifacts"]["refs"] == []
    assert first["provenance"] is None
    assert first["ambiguity"] is None
    assert first["provider"]["available"] is True
    assert first["provider"]["capabilities"] == sorted(first["provider"]["capabilities"])


def test_cli_projects_the_same_semantic_snapshot(tmp_path, capsys):
    workflow = {
        "id": "inspect",
        "tasks": [
            {
                "id": "a",
                "operation": {
                    "type": "process",
                    "executable": "python",
                },
            }
        ],
    }
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(workflow), encoding="utf-8")

    assert main(["inspect", str(path), "--json"]) == EXIT_SUCCESS
    payload = json.loads(capsys.readouterr().out)

    assert payload["workflow"]["id"] == "inspect"
    assert payload["execution"]["performed"] is False
    assert payload["lifecycle"]["observed"] is False
    assert payload["process"]["observed"] is False
    assert payload["identity"]["attempt_identity"] == "assigned-at-execution"
