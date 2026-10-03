from marsh.core.domain import ProcessStatus, Result, Task, Workflow
from marsh.core.runtime import execute_workflow
from marsh.core.serialization import workflow_from_json, workflow_to_json


def test_result_is_structured_and_round_trippable_as_runtime_data():
    result = Result(
        stdout=b"out",
        stderr=b"err",
        exit_code=0,
        status=ProcessStatus.COMPLETED,
        metadata={"attempt": 1},
    )

    assert result.ok
    assert not result.failed
    assert result.exit_code == 0
    assert result.metadata["attempt"] == 1


def test_workflow_serialization_is_deterministic_and_round_trips():
    workflow = Workflow(
        id="serialize",
        tasks=(
            Task(
                id="b",
                operation="operation-b",
                dependencies=("a",),
                inputs={"z": 1, "a": 2},
            ),
            Task(id="a", operation="operation-a"),
        ),
        metadata={"z": 1, "a": 2},
    )

    first = workflow_to_json(workflow)
    second = workflow_to_json(workflow)
    restored = workflow_from_json(first)

    assert first == second
    assert restored.id == workflow.id
    assert tuple(task.id for task in restored.tasks) == ("a", "b")
    assert restored.task("b").dependencies == ("a",)
    assert restored.metadata == {"a": 2, "z": 1}


def test_dependency_results_are_the_minimal_task_dataflow():
    seen = []

    def producer(inputs, dependencies):
        return Result(stdout=b"value")

    def consumer(inputs, dependencies):
        seen.append(dependencies["producer"].stdout)
        return Result(stdout=dependencies["producer"].stdout + b"-next")

    workflow = Workflow(
        id="dataflow",
        tasks=(
            Task(id="consumer", operation=consumer, dependencies=("producer",)),
            Task(id="producer", operation=producer),
        ),
    )

    results = execute_workflow(workflow)

    assert seen == [b"value"]
    assert results["consumer"].stdout == b"value-next"
