# Marsh API and Migration Guide

This guide explains the public API boundary introduced by the v0.3.x workflow kernel and how existing applications can migrate incrementally without abandoning compatible legacy APIs.

## 1. Public API boundary

For new workflow-oriented code, prefer the modern namespaces:

```python
from marsh import (
    ProcessSpec,
    Task,
    Workflow,
    execute_workflow,
    plan_workflow,
    validate_workflow,
)
```

The explicit namespace form is:

```python
from marsh.workflow import Task, Workflow
from marsh.runtime import execute_workflow, plan_workflow
from marsh.providers import LocalProvider
```

The root `marsh` exports remain supported for compatibility and convenience.

The current implementation keeps the modern namespace modules as thin boundaries over the existing kernel implementation. This is intentional: the v0.3.x migration establishes clearer contracts without requiring a wholesale package move.

## 2. What to use for new code

| Need | Modern API |
| --- | --- |
| Define workflow | `Workflow` |
| Define unit of work | `Task` |
| Describe a process | `ProcessSpec` |
| Validate structure | `validate_workflow()` |
| Get deterministic plan | `plan_workflow()` |
| Execute | `execute_workflow()` |
| Inspect outcome | `Result` |
| Inspect validation diagnostics | `validate_workflow_diagnostics()` |
| Mapping/JSON normalization | `WorkflowConfig`, `TaskConfig`, serialization helpers |
| Provider capability boundary | `marsh.providers` |

The canonical runtime currently uses sequential local execution. Remote, Docker, command-composition, and DAG mechanisms remain available through their existing APIs.

## 3. Migration from legacy command composition

Existing code such as:

```python
from marsh.core import Conveyor

conveyor = Conveyor().add_cmd_runner(command)
stdout, stderr = conveyor()
```

does not need to be rewritten merely because the Workflow API exists.

For a new workflow, introduce a `Task` around an explicit `ProcessSpec`:

```python
from marsh import ProcessSpec, Task, Workflow, execute_workflow

workflow = Workflow(
    id="hello",
    tasks=(
        Task(
            id="greet",
            operation=ProcessSpec(
                executable="python",
                arguments=("-c", "print('hello')"),
            ),
        ),
    ),
)

results = execute_workflow(workflow)
result = results["greet"]
```

Use the legacy `Conveyor` surface when direct command-runner composition is itself the application requirement. Use `Workflow` when the application needs explicit lifecycle, dependency, validation, planning, or structured-result semantics.

## 4. Migration from legacy executors

Existing executor classes remain compatibility surfaces. Do not replace them mechanically.

A safe migration is:

1. Keep the existing executor behavior covered by tests.
2. Represent new workflow intent with `Workflow` and `Task`.
3. Represent process parameters with `ProcessSpec` where applicable.
4. Use planning and validation before execution.
5. Adapt the existing executor/provider at the runtime boundary when integration is required.
6. Migrate individual call sites only when the new contract provides a concrete benefit.

The goal is an adapter/translation migration, not a flag-day rewrite.

## 5. Migration from DAG APIs

The existing DAG API remains supported:

```python
from marsh.dag import Node, SyncDag
```

Use DAG primitives when an application directly needs their existing execution behavior or compatibility.

For new workflow-domain code, prefer:

```text
Workflow
   |
   v
canonical execution plan
   |
   v
scheduler
   |
   v
existing execution mechanisms
```

The Workflow model and DAG model should not become two independent dependency engines. Workflow dependencies describe domain intent; scheduling uses a canonical dependency ordering. Existing DAG APIs remain low-level compatibility infrastructure.

## 6. Legacy namespace compatibility

Older imports such as:

```python
from marsh.core import Conveyor
from marsh.core.executor import LocalCommandExecutor
from marsh.dag import SyncDag
```

remain valid compatibility surfaces in the current release line.

The `marsh.core` namespace should be treated as a compatibility surface rather than the preferred mixed namespace for new workflow features.

Do not remove or rename legacy imports as part of ordinary feature work. A legacy API should only be deprecated when all of the following exist:

- an equivalent supported capability;
- migration documentation;
- compatibility tests covering the old import/behavior;
- a deliberate deprecation notice and transition path.

## 7. Lifecycle and failure semantics

The canonical process lifecycle uses explicit statuses:

```text
CREATED -> STARTING -> RUNNING -> terminal state
                         |
                         +-> STOPPING -> terminal state
```

Terminal outcomes include `COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT`, and `SKIPPED`.

Dependent tasks do not execute normally when an upstream result is non-completed under the default dependency policy; they receive a skipped result. Failure policy and retry/timeout policies remain explicit runtime concerns.

Applications should inspect `Result.status`, `Result.error`, and `Result.ok` rather than treating a non-empty stderr stream as proof of failure.

## 8. Validation, planning, and execution

Keep these stages separate:

```python
workflow = ...
validate_workflow(workflow)
plan = plan_workflow(workflow)

# Review plan before execution if desired.
results = execute_workflow(workflow)
```

Validation catches structural and dependency errors before work starts. Planning provides deterministic ordering and readiness information. Execution performs the actual work.

This separation is the preferred seam for future schedulers and execution mechanisms.

## 9. Configuration and serialization

For data-oriented authoring:

```python
from marsh import (
    workflow_from_dict,
    workflow_from_json,
    workflow_to_dict,
    workflow_to_json,
)

workflow = workflow_from_dict(config)
payload = workflow_to_json(workflow)
round_trip = workflow_from_json(payload)
```

Portable JSON definitions should contain serializable values. Arbitrary Python callables are Python objects and are not general portable JSON definitions.


## 10. Artifacts, identity, and provenance

v0.3.8 adds identity and artifact fields additively to canonical Result values:

    result.execution_id
    result.attempt_id
    result.artifact_refs
    result.provenance

Existing code that only reads stdout, stderr, status, error, duration, or metadata does not need to change.

For portable workflows, execution_id is deterministic across fresh processes. Retry attempts keep the same execution identity while receiving a distinct attempt identity. Cache hits reuse the successful cached result rather than creating another attempt.

Artifact persistence is opt-in:

    store = LocalArtifactStore(".marsh-artifacts")
    results = execute_workflow(workflow, artifact_store=store)

Applications that require portability should avoid arbitrary local/lambda callables in workflow definitions. Legacy callable workflows remain supported, but the runtime does not invent a portable execution identity for definitions that cannot cross the canonical serialization boundary.

## 11. Deprecation discipline

The v0.3.x compatibility policy is deliberately conservative:

- preserve existing public behavior where practical;
- prefer additive modern boundaries;
- use adapters rather than invasive rewrites;
- document migration before deprecation;
- add compatibility tests before removing a surface;
- do not remove legacy DAG/executor APIs simply because Workflow has a higher-level representation.

This policy keeps application migrations incremental while the workflow kernel continues to converge.

## 12. Further reading

- [Workflow Guide](../tutorials/workflow.md) — canonical examples and workflow semantics.
- [Architecture](../concepts/architecture.md) — implemented architecture and boundaries.
- [Samples](../../samples/) — runnable canonical examples.
