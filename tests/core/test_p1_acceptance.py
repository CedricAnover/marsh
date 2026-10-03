from marsh.core.configuration import normalize_workflow
from marsh.core.domain import ProcessStatus, Result
from marsh.core.runtime import execute_workflow, plan_workflow
from marsh.core.validation import validate_workflow_diagnostics


def test_p1_workflow_boundary_plan_execute_acceptance():
    def produce(inputs, dependencies):
        return Result(stdout=b"ok")

    workflow_config = {
        "id": "p1-acceptance",
        "tasks": [
            {"id": "produce", "operation": produce, "outputs": ["artifact"]},
            {
                "id": "consume",
                "operation": lambda inputs, dependencies: Result(
                    stdout=dependencies["produce"].stdout + b"-consumed"
                ),
                "dependencies": ["produce"],
            },
        ],
    }

    assert validate_workflow_diagnostics(workflow_config) == ()

    workflow = normalize_workflow(workflow_config)
    plan = plan_workflow(workflow)
    assert plan.order == ("produce", "consume")
    assert plan.ready == ("produce",)

    results = execute_workflow(workflow)

    assert results["produce"].status is ProcessStatus.COMPLETED
    assert results["consume"].status is ProcessStatus.COMPLETED
    assert results["consume"].stdout == b"ok-consumed"
