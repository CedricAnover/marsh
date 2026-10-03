# Marsh Workflow Guide

This guide is the dependency-free Markdown entry point for the canonical Marsh Workflow API.

## 1. The canonical flow

A workflow follows a deliberate lifecycle:

\x60\x60\x60text
Workflow definition
      |
      v
Validation
      |
      v
Execution plan
      |
      v
Scheduler
      |
      v
Process / provider execution
      |
      v
Structured Result objects
\x60\x60\x60

The public API separates **what work means** from **how work is executed**:

- \x60Workflow\x60 and \x60Task\x60 describe workflow intent.
- \x60ProcessSpec\x60 describes an executable process.
- Validation rejects malformed workflow structure before execution.
- Planning exposes deterministic execution order and readiness.
- The scheduler controls execution order.
- Providers/executors perform the actual work.
- \x60Result\x60 records execution outcome and diagnostics.

The current canonical runtime is intentionally **sequential and local**. Existing SSH, Docker, Python, command-composition, and DAG APIs remain compatibility surfaces.

See [the architecture overview](architecture.md) for the implemented boundaries.

## 2. Minimal workflow

The smallest useful workflow uses \x60Workflow\x60, \x60Task\x60, and \x60ProcessSpec\x60:

\x60\x60\x60python
import sys

from marsh import ProcessSpec, Task, Workflow, execute_workflow

workflow = Workflow(
    id="hello",
    tasks=(
        Task(
            id="greet",
            operation=ProcessSpec(
                executable=sys.executable,
                arguments=("-c", "print('hello from Marsh')"),
            ),
        ),
    ),
)

results = execute_workflow(workflow)
result = results["greet"]

if not result.ok:
    raise RuntimeError(result.error)

print(result.stdout.decode().strip())
\x60\x60\x60

The repository version of this example is [\x60samples/workflow_basic.py\x60](../samples/workflow_basic.py).

## 3. Validate before executing

Validation is an explicit boundary:

\x60\x60\x60python
from marsh import validate_workflow

order = validate_workflow(workflow)
print(order)
\x60\x60\x60

Validation covers the workflow structure and dependency semantics, including:

- task identifier validity;
- dependency references; and
- dependency cycles.

Validation is deterministic. Applications can therefore reject an invalid definition before starting execution.

The planning example is [\x60samples/workflow_plan.py\x60](../samples/workflow_plan.py).

## 4. Inspect the execution plan

Use \x60plan_workflow()\x60 when an application needs to inspect execution without starting it:

\x60\x60\x60python
from marsh import plan_workflow

plan = plan_workflow(workflow)

print(plan.order)
print(plan.ready)
\x60\x60\x60

The execution plan is the canonical bridge between workflow semantics and scheduling. The intent is:

\x60\x60\x60text
Workflow
   |
   v
canonical execution plan
   |
   v
scheduler
\x60\x60\x60

This avoids creating a second independent dependency engine.

## 5. Dependencies and failure propagation

Tasks declare dependencies explicitly:

\x60\x60\x60python
Task(
    id="test",
    operation=...,
    dependencies=("build",),
)
\x60\x60\x60

For a simple dependency:

\x60\x60\x60text
build ---> test
\x60\x60\x60

The default runtime propagates a non-completed upstream result to dependent tasks according to the configured dependency policy. This means downstream work is not silently executed when its prerequisite did not complete successfully.

The repository regression coverage is represented by [\x60samples/workflow_failure_skip.py\x60](../samples/workflow_failure_skip.py) and the corresponding runtime tests.

## 6. Results

Canonical workflow execution returns structured \x60Result\x60 objects:

\x60\x60\x60python
results = execute_workflow(workflow)
result = results["greet"]

print(result.status)
print(result.exit_code)
print(result.stdout)
print(result.stderr)
print(result.error)
print(result.duration)
print(result.metadata)
print(result.ok)
\x60\x60\x60

A non-empty \x60stderr\x60 is not, by itself, a failure signal. Consumers should use the structured status, exit code, error information, and applicable execution semantics.

## 7. Serialization and configuration

Workflow definitions can be represented as mappings and JSON:

\x60\x60\x60python
from marsh import (
    workflow_from_dict,
    workflow_from_json,
    workflow_to_dict,
    workflow_to_json,
)

workflow = workflow_from_dict(
    {
        "id": "hello",
        "tasks": [
            {
                "id": "greet",
                "operation": {
                    "executable": "python",
                    "arguments": ["-c", "print('hello')"],
                },
            }
        ],
    }
)

payload = workflow_to_dict(workflow)
encoded = workflow_to_json(workflow)

assert workflow_to_dict(workflow_from_json(encoded)) == payload
\x60\x60\x60

Use data-oriented workflow definitions when portability or persistence matters. Arbitrary Python callables are Python objects and are not general portable JSON definitions.

See:

- [\x60samples/workflow_serialization.py\x60](../samples/workflow_serialization.py)
- [\x60samples/workflow_config.py\x60](../samples/workflow_config.py)
- [\x60samples/workflow_ir_sample.py\x60](../samples/workflow_ir_sample.py)

## 8. Minimal dataflow

The workflow model is converging dependency semantics and task dataflow through the same canonical execution representation rather than introducing a parallel graph runtime.

For example:

\x60\x60\x60text
producer task
    |
    | declared dependency/data relationship
    v
canonical execution graph / plan
    |
    v
consumer task
\x60\x60\x60

The current implementation keeps this intentionally minimal. General automatic output-to-input data passing should not be assumed unless the relevant workflow contract explicitly provides it.

See [\x60samples/workflow_dependency_results.py\x60](../samples/workflow_dependency_results.py) for the current dependency/result behavior.

## 9. ProcessSpec

\x60ProcessSpec\x60 describes process execution without performing it:

\x60\x60\x60python
ProcessSpec(
    executable="python",
    arguments=("-c", "print('hello')"),
    environment={"MODE": "development"},
    working_directory="/tmp",
    timeout=30,
)
\x60\x60\x60

Keeping this description separate from execution allows validation, planning, serialization, and execution to remain independently testable.

## 10. Existing APIs and compatibility

Marsh retains its established lower-level APIs:

- \x60Conveyor\x60 and command runners;
- processors and modifiers;
- local, SSH, Docker, and Python executors;
- \x60Node\x60 and DAG implementations.

New workflow functionality should prefer the canonical Workflow contracts and adapt existing mechanisms rather than creating another execution model.

For migration-oriented examples and the full public surface, start with the [repository README](../README.md).

## 11. Recommended application pattern

For new applications, use this sequence:

\x60\x60\x60python
workflow = build_workflow()

validate_workflow(workflow)

plan = plan_workflow(workflow)

# Optional: inspect or approve plan here.

results = execute_workflow(workflow)

for task_id, result in results.items():
    if not result.ok:
        handle_failure(task_id, result)
\x60\x60\x60

The separation is intentional:

1. **Define** — construct the workflow.
2. **Validate** — reject invalid structure and dependencies.
3. **Plan** — inspect deterministic execution order/readiness.
4. **Execute** — run through the canonical scheduler/runtime.
5. **Inspect results** — consume structured outcomes.

## 12. Current boundaries

The current Alpha implementation has deliberate limits:

- canonical execution is local and sequential;
- general task-to-task output/input dataflow is limited;
- there is no standalone canonical workflow CLI;
- YAML authoring is not currently provided;
- callable operations are Python-specific and are not portable JSON definitions;
- remote/container execution remains available through existing APIs rather than the canonical local runtime.

These are implementation boundaries, not a reason to introduce a second workflow engine.

## 13. Developer verification

Install the development environment:

\x60\x60\x60bash
uv sync --all-groups
\x60\x60\x60

Run the test suite:

\x60\x60\x60bash
uv run pytest -vv --disable-warnings --tb=short
\x60\x60\x60

Run linting:

\x60\x60\x60bash
uv run pflake8
\x60\x60\x60

Build the package:

\x60\x60\x60bash
uv build
\x60\x60\x60

Canonical examples live under [\x60samples/\x60](../samples/).

## 14. Architecture reference

The implemented architecture can be summarized as:

\x60\x60\x60mermaid
flowchart TD
    A[Workflow / Task] --> B[Validation]
    B --> C[Execution Plan]
    C --> D[Scheduler]
    D --> E[Process / Provider]
    E --> F[Structured Result]
\x60\x60\x60

The existing DAG and command APIs are low-level compatibility mechanisms. The canonical direction is:

\x60\x60\x60text
Workflow
  -> canonical execution graph/plan
  -> scheduler/DAG primitive
  -> existing executors/providers
\x60\x60\x60

This keeps dependency ordering in one conceptual path while allowing existing APIs to remain compatible during incremental migration.
