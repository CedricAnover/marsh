import pytest

from marsh.core.domain import ProcessStatus, Result, Task, Workflow
from marsh.core.runtime import execute_workflow


def test_execute_workflow_propagates_failure_transitively():
    seen = []

    def fail(inputs, dependencies):
        seen.append("fail")
        return Result(status=ProcessStatus.FAILED, error="boom")

    def direct(inputs, dependencies):
        seen.append("direct")
        return Result(stdout=b"unexpected")

    def transitive(inputs, dependencies):
        seen.append("transitive")
        return Result(stdout=b"unexpected")

    workflow = Workflow(
        id="transitive-failure",
        tasks=(
            Task(id="transitive", operation=transitive, dependencies=("direct",)),
            Task(id="direct", operation=direct, dependencies=("fail",)),
            Task(id="fail", operation=fail),
        ),
    )

    results = execute_workflow(workflow)

    assert results["fail"].status is ProcessStatus.FAILED
    assert results["direct"].status is ProcessStatus.SKIPPED
    assert results["transitive"].status is ProcessStatus.SKIPPED
    assert results["direct"].error == "dependency failed: fail"
    assert results["transitive"].error == "dependency failed: direct"
    assert seen == ["fail"]


@pytest.mark.parametrize("status", [ProcessStatus.CANCELLED, ProcessStatus.TIMED_OUT])
def test_execute_workflow_skips_dependents_for_non_success_terminal_results(status):
    seen = []

    def upstream(inputs, dependencies):
        seen.append("upstream")
        return Result(status=status, error=status.value)

    def dependent(inputs, dependencies):
        seen.append("dependent")
        return Result(stdout=b"unexpected")

    workflow = Workflow(
        id=f"terminal-{status.value}",
        tasks=(
            Task(id="dependent", operation=dependent, dependencies=("upstream",)),
            Task(id="upstream", operation=upstream),
        ),
    )

    results = execute_workflow(workflow)

    assert results["upstream"].status is status
    assert results["dependent"].status is ProcessStatus.SKIPPED
    assert results["dependent"].error == f"dependency failed: upstream"
    assert seen == ["upstream"]
