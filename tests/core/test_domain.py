import pytest

from marsh.core.domain import (
    Machine,
    Process,
    ProcessSpec,
    ProcessStatus,
    Result,
    Scheduler,
    Startable,
    Task,
    Waitable,
    Workflow,
    can_transition,
)


def test_process_spec_is_reified_and_validated():
    spec = ProcessSpec(
        executable="python",
        arguments=("-c", "print('ok')"),
        environment={"MODE": "test"},
        working_directory="/tmp",
        timeout=5.0,
    )

    assert spec.executable == "python"
    assert spec.arguments == ("-c", "print('ok')")
    assert spec.environment == {"MODE": "test"}
    assert spec.timeout == 5.0

    with pytest.raises(ValueError, match="executable"):
        ProcessSpec(executable="")

    with pytest.raises(ValueError, match="timeout"):
        ProcessSpec(executable="python", timeout=0)


def test_result_does_not_equate_stderr_with_failure():
    result = Result(
        stdout=b"ok",
        stderr=b"warning",
        exit_code=0,
        status=ProcessStatus.COMPLETED,
    )

    assert result.ok is True
    assert result.failed is False
    assert result.stderr == b"warning"


def test_result_failure_is_structured():
    result = Result(
        stdout=b"",
        stderr=b"boom",
        exit_code=2,
        status=ProcessStatus.FAILED,
        error="command failed",
    )

    assert result.ok is False
    assert result.failed is True
    assert result.error == "command failed"


def test_lifecycle_transition_rules_are_explicit():
    assert can_transition(ProcessStatus.CREATED, ProcessStatus.STARTING)
    assert can_transition(ProcessStatus.STARTING, ProcessStatus.RUNNING)
    assert can_transition(ProcessStatus.RUNNING, ProcessStatus.COMPLETED)
    assert can_transition(ProcessStatus.RUNNING, ProcessStatus.FAILED)
    assert can_transition(ProcessStatus.RUNNING, ProcessStatus.CANCELLED)
    assert can_transition(ProcessStatus.RUNNING, ProcessStatus.TIMED_OUT)
    assert not can_transition(ProcessStatus.COMPLETED, ProcessStatus.RUNNING)
    assert not can_transition(ProcessStatus.FAILED, ProcessStatus.STOPPING)


def test_workflow_and_task_contracts_are_small_and_explicit():
    task_a = Task(id="a", operation="echo")
    task_b = Task(id="b", operation="echo", dependencies=("a",))
    workflow = Workflow(id="example", tasks=(task_a, task_b))

    assert workflow.task("a") is task_a
    assert workflow.task("b").dependencies == ("a",)

    with pytest.raises(ValueError, match="duplicate"):
        Workflow(id="bad", tasks=(task_a, task_a))

    with pytest.raises(ValueError, match="unknown"):
        Workflow(id="bad", tasks=(Task(id="b", operation="echo", dependencies=("missing",)),))


def test_capability_protocols_are_structural():
    class FakeProcess:
        def start(self):
            return None

        def wait(self):
            return Result(status=ProcessStatus.COMPLETED)

    class FakeMachine:
        def create_process(self, spec):
            return FakeProcess()

    class FakeScheduler:
        def schedule(self, workflow):
            return workflow.tasks

    assert isinstance(FakeProcess(), Startable)
    assert isinstance(FakeProcess(), Waitable)
    assert isinstance(FakeMachine(), Machine)
    assert isinstance(FakeScheduler(), Scheduler)
    assert isinstance(FakeProcess(), Process)


def test_process_protocol_can_expose_optional_capabilities_without_universal_methods():
    class MinimalProcess:
        def start(self):
            return None

        def wait(self):
            return Result(status=ProcessStatus.COMPLETED)

    assert isinstance(MinimalProcess(), Startable)
    assert isinstance(MinimalProcess(), Waitable)
