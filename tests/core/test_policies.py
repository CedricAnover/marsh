import sys

from marsh.core.domain import ProcessSpec, ProcessStatus, Result, Task, Workflow
from marsh.core.policies import (
    CleanupPolicy,
    ExecutionPolicy,
    FailureClass,
    RetryPolicy,
    TimeoutPolicy,
    evaluate_policy,
)
from marsh.core.runtime import execute_workflow


def test_policy_precedence_blocks_retry_after_cleanup_failure():
    policy = ExecutionPolicy(
        retry=RetryPolicy(max_attempts=3),
        cleanup=CleanupPolicy(block_retry_on_failure=True),
    )
    result = Result(status=ProcessStatus.FAILED, metadata={"failure_class": "transient"})

    decision = evaluate_policy(
        policy,
        result,
        attempt=1,
        cleanup_succeeded=False,
    )

    assert decision.failure_class is FailureClass.TRANSIENT
    assert decision.retry is False
    assert decision.cleanup_blocks_retry is True


def test_retry_records_distinct_attempt_identity():
    attempts = []

    def operation(inputs, dependencies):
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            return Result(status=ProcessStatus.FAILED, metadata={"failure_class": "transient"})
        return Result(stdout=b"ok")

    workflow = Workflow(
        id="attempts",
        tasks=(Task(id="task", operation=operation),),
    )

    result = execute_workflow(
        workflow,
        policy=ExecutionPolicy(retry=RetryPolicy(max_attempts=2)),
    )["task"]

    assert attempts == [1, 2]
    assert result.ok
    assert result.metadata["attempt"] == 2
    assert result.metadata["attempt_id"] == "task:2"


def test_non_idempotent_task_is_not_retried_by_default():
    attempts = []

    def operation(inputs, dependencies):
        attempts.append(1)
        return Result(status=ProcessStatus.FAILED, metadata={"failure_class": "transient"})

    workflow = Workflow(
        id="unsafe-retry",
        tasks=(Task(id="task", operation=operation, metadata={"idempotent": False}),),
    )

    result = execute_workflow(
        workflow,
        policy=ExecutionPolicy(retry=RetryPolicy(max_attempts=3)),
    )["task"]

    assert len(attempts) == 1
    assert result.status is ProcessStatus.FAILED
    assert result.metadata["attempt"] == 1


def test_cleanup_runs_once_per_attempt_before_retry():
    calls = []

    def cleanup(task, attempt):
        calls.append(attempt)

    def operation(inputs, dependencies):
        if len(calls) == 0:
            return Result(status=ProcessStatus.FAILED, metadata={"failure_class": "transient"})
        return Result(stdout=b"ok")

    workflow = Workflow(
        id="cleanup",
        tasks=(Task(id="task", operation=operation, metadata={"cleanup": cleanup}),),
    )

    result = execute_workflow(
        workflow,
        policy=ExecutionPolicy(retry=RetryPolicy(max_attempts=2)),
    )["task"]

    assert result.ok
    assert calls == [1, 2]


def test_workflow_policy_round_trips_through_v1_ir():
    from marsh.core.serialization import workflow_from_dict, workflow_to_dict

    workflow = Workflow(
        id="ir-policy",
        tasks=(
            Task(
                id="task",
                operation=ProcessSpec(executable=sys.executable, arguments=("-c", "print('ok')")),
            ),
        ),
        policy=ExecutionPolicy(
            retry=RetryPolicy(max_attempts=2),
            timeout=TimeoutPolicy(1.0),
        ).to_mapping(),
    )

    payload = workflow_to_dict(workflow)
    restored = workflow_from_dict(payload)

    assert restored.policy["retry"]["max_attempts"] == 2
    assert restored.policy["timeout"]["timeout"] == 1.0
