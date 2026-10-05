import sys

from marsh.core.artifact_store import LocalArtifactStore
from marsh.core.cache import MemoryCache
from marsh.core.domain import ProcessSpec, ProcessStatus, Result, Task, Workflow
from marsh.core.policies import ExecutionPolicy, RetryPolicy
from marsh.core.runtime import execute_workflow


def emit_payload(inputs, dependencies):
    return Result(stdout=b"payload")


_retry_calls = 0


def retry_operation(inputs, dependencies):
    global _retry_calls
    _retry_calls += 1
    if _retry_calls == 1:
        return Result(
            status=ProcessStatus.FAILED,
            metadata={"failure_class": "transient"},
        )
    return Result(stdout=b"ok")


def test_retry_keeps_execution_identity_but_changes_attempt_identity(tmp_path):
    global _retry_calls
    _retry_calls = 0

    workflow = Workflow(
        id="identity",
        tasks=(Task(id="task", operation=retry_operation),),
    )

    result = execute_workflow(
        workflow,
        policy=ExecutionPolicy(retry=RetryPolicy(max_attempts=2)),
        artifact_store=LocalArtifactStore(tmp_path),
    )["task"]

    assert result.ok
    assert result.execution_id
    assert result.attempt_id == "task:2"
    assert result.provenance["execution_id"] == result.execution_id
    assert len(result.artifact_refs) == 1


def test_cache_hit_reuses_execution_identity_without_creating_attempt():
    workflow = Workflow(
        id="cache-identity",
        tasks=(
            Task(
                id="task",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "print('cached')"),
                ),
            ),
        ),
    )
    cache = MemoryCache()
    policy = ExecutionPolicy.from_mapping(
        {"cache": {"enabled": True, "namespace": "v038"}}
    )

    first = execute_workflow(workflow, policy=policy, cache=cache)["task"]
    second = execute_workflow(workflow, policy=policy, cache=cache)["task"]

    assert first.execution_id == second.execution_id
    assert second.attempt_id == first.attempt_id


def test_artifact_reference_can_be_verified_from_provenance(tmp_path):
    store = LocalArtifactStore(tmp_path)
    workflow = Workflow(
        id="artifact",
        tasks=(Task(id="task", operation=emit_payload),),
    )

    result = execute_workflow(workflow, artifact_store=store)["task"]

    reference = result.artifact_refs[0]
    assert store.verify(reference)
    assert reference.digest in result.provenance["output_artifact_refs"]
