# Marsh

**Marsh** is a lightweight, extensible Python library for building, validating, planning, and executing command workflows.

Marsh separates **workflow definition** from **execution**. Work can be represented explicitly, validated before execution, inspected as an execution plan, and then executed through a runtime.

The project is evolving toward a small, dependency-light workflow and execution kernel while preserving its existing command, executor, and DAG APIs.

> **Current release:** v0.4.3 — observability & operational readiness. Marsh now exposes correlated runtime evidence, stable operational diagnostics, secret-safe observer boundaries, and an optional OpenTelemetry API adapter without adding a mandatory telemetry dependency. See [the semantic contract](docs/concepts/semantic-contracts.md) and [the observability documentation](docs/concepts/observability.md).

> **Project status:** Alpha

## Features

- **Workflow API** — define workflows with `Workflow`, `Task`, and `ProcessSpec`.
- **Validation and planning** — validate dependencies and inspect deterministic execution order before running.
- **Structured results** — execution produces structured `Result` objects rather than relying only on `(stdout, stderr)` tuples.
- **Command composition** — compose command runners with `Conveyor`.
- **Processors and modifiers** — add validation, logging, transformation, and other reusable command behavior.
- **DAG workflows** — model dependencies with the existing DAG API.
- **Multiple execution mechanisms** — local, SSH, Docker, and Python execution are available through existing APIs.
- **Composable architecture** — workflow semantics are separated from execution mechanisms and policies.

## Requirements

Marsh currently supports:

- Python 3.10
- Python 3.11
- Python 3.12

The core package has no runtime dependencies. Optional integrations are available through extras:

- `marsh-lib[ssh]` — Fabric-based SSH integration.
- `marsh-lib[docker]` — Docker integration.

The v0.4.1 remote boundary is transport-neutral; it does not require a remote transport dependency in core.

## Installation

Install the package from PyPI:

```bash
pip install marsh-lib
```

For development:

```bash
uv sync --all-groups
```

## Quick start

For new code, the **canonical Workflow API** is the recommended starting point.

```python
import sys

from marsh import (
    ProcessSpec,
    Task,
    Workflow,
    execute_workflow,
    plan_workflow,
    validate_workflow,
)

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

# Validate the workflow and obtain deterministic task order.
order = validate_workflow(workflow)

# Inspect the execution plan before running anything.
plan = plan_workflow(workflow)

print(order)
print(plan.ready)

# Execute the workflow.
results = execute_workflow(workflow)

result = results["greet"]

if not result.ok:
    raise RuntimeError(result.error)

print(result.stdout.decode().strip())
```

A complete runnable example is available in [`samples/workflow_ir_sample.py`](samples/workflow_ir_sample.py).

## Remote execution readiness

v0.4.1 defines the semantic boundary required for remote execution without committing Marsh to a production transport. The boundary separates:

- `Machine` — execution environment;
- `MachineConnection` — transport/session concerns;
- `ExecutionSubstrate` — machine-side execution capability;
- `Agent` — optional machine-side execution endpoint;
- `ExecutionRequest` / `ExecutionResponse` — identity-preserving boundary messages.

Remote failures are not automatically classified as process failures. If a transport failure occurs without authoritative execution evidence, Marsh preserves an ambiguous outcome instead of guessing.

A small standard-library TCP adapter is included as a conformance/reference mechanism. It is evidence for the boundary, not a production transport commitment.

## Observability

Runtime observability is opt-in and downstream of canonical execution semantics. Events can correlate workflow, task, execution, attempt, provider, and process identities while preserving `UNKNOWN`/`AMBIGUOUS` evidence and redacting secrets before observers receive data. See [Observability](docs/concepts/observability.md).

```python
from marsh import execute_workflow

class Printer:
    def on_event(self, event):
        print(event.to_dict())

results = execute_workflow(workflow, observers=(Printer(),))
```

Observers cannot alter execution outcomes, and OpenTelemetry integration is optional through the API-only `OpenTelemetryObserver`. Applications own SDK/exporter configuration.

## Core concepts

### Workflow

A `Workflow` is the top-level representation of work.

```python
Workflow(
    id="pipeline",
    tasks=(...),
    inputs={...},
    outputs={...},
    metadata={...},
)
```

A workflow describes **what should happen** without coupling the definition to a particular execution mechanism.

### Task

A `Task` represents one unit of work and its dependencies.

```python
Task(
    id="test",
    operation=...,
    dependencies=("build",),
)
```

Dependencies currently express execution ordering.

The canonical runtime does not yet provide general automatic output-to-input dataflow between dependent tasks.

### ProcessSpec

`ProcessSpec` describes a process without executing it.

```python
ProcessSpec(
    executable="python",
    arguments=("-c", "print('hello')"),
    environment={"MODE": "development"},
    working_directory="/tmp",
    timeout=30,
)
```

Keeping process descriptions explicit makes them easier to validate, inspect, serialize, and execute through different mechanisms.

### Result

Canonical workflow execution returns structured results.

A result can contain:

```python
result.stdout
result.stderr
result.exit_code
result.status
result.error
result.duration
result.metadata
result.ok
```

A non-empty `stderr` does **not** automatically mean that execution failed. Failure is represented by execution status, exit code, exceptions, timeouts, provider errors, or other applicable execution semantics.

## Validate before executing

Workflow validation is separate from execution:

```python
order = validate_workflow(workflow)
```

Validation checks workflow structure and dependency semantics, including:

- task identifiers;
- dependency references;
- dependency cycles.

The returned order is deterministic.

This allows applications to reject invalid workflows before executing them.

## Inspect the execution plan

Use `plan_workflow()` when the application needs to inspect execution before starting it:

```python
plan = plan_workflow(workflow)

print(plan.order)
print(plan.ready)
```

The current execution plan exposes the deterministic task order and initially ready tasks.

## Execute a workflow

Execute a validated workflow with:

```python
results = execute_workflow(workflow)
```

The canonical runtime supports deterministic sequential execution and bounded concurrent execution.

Conceptually:

    Workflow
        |
        v
    Validation / Planning
        |
        v
    Scheduler State Machine
        |
        +--> Sequential Scheduler
        +--> Async Scheduler
        +--> Thread Scheduler
        +--> Process Scheduler
        |
        v
    Execution Mechanism
        |
        v
    Structured Results

Concurrent schedulers share the same dependency semantics and bounded ready-queue state machine. The scheduler controls readiness and dispatch; execution mechanisms remain responsible for running individual tasks.

For async execution, use `execute_workflow_async()`. For bounded thread or process execution, pass `ThreadScheduler(max_concurrency=...)` or `ProcessScheduler(max_concurrency=...)` to `execute_workflow()`.

The workflow model is intentionally separated from the runtime so additional scheduling and execution mechanisms can be introduced without creating another workflow engine.

## Workflow dependencies

Dependencies are declared explicitly:

```python
workflow = Workflow(
    id="pipeline",
    tasks=(
        Task(
            id="build",
            operation=ProcessSpec(
                executable="python",
                arguments=("-c", "print('build')"),
            ),
        ),
        Task(
            id="test",
            operation=ProcessSpec(
                executable="python",
                arguments=("-c", "print('test')"),
            ),
            dependencies=("build",),
        ),
    ),
)
```

The dependency graph is validated before execution.

For the example above, the dependency relationship is:

    build
      |
      v
    test

The current canonical scheduler executes tasks sequentially in deterministic topological order.

## Mapping and JSON workflows

Workflow definitions can be normalized from mappings and JSON:

```python
from marsh import (
    workflow_from_dict,
    workflow_from_json,
    workflow_to_dict,
    workflow_to_json,
)
```

For example:

```python
workflow = workflow_from_dict(
    {
        "id": "hello",
        "tasks": [
            {
                "id": "greet",
                "operation": ...,
            }
        ],
    }
)
```

Data-oriented workflow definitions are preferred when serialization or portability is required.

Arbitrary Python callables are Python objects and therefore are not general portable JSON representations.

## Existing command API

Marsh's original command-composition API remains available.

### `Conveyor`

`Conveyor` chains command runners together.

```python
from marsh import Conveyor

def uppercase(stdout, stderr):
    return stdout.upper(), stderr

def lowercase_error(stdout, stderr):
    return stdout, stderr.lower()

conveyor = (
    Conveyor()
    .add_cmd_runner(uppercase)
    .add_cmd_runner(lowercase_error)
)

stdout, stderr = conveyor(b"hello", b"ERROR")

assert stdout == b"HELLO"
assert stderr == b"error"
```

`Conveyor` is useful when applications need direct command-runner composition without the higher-level workflow model.

## Processors and modifiers

Marsh supports reusable pre/post processing around command runners.

### Processors

Processors perform an action without replacing the `(stdout, stderr)` values.

Typical uses include:

- validation;
- logging;
- metrics;
- inspection.

```python
from marsh import CmdRunDecorator

def validate(stdout, stderr):
    assert not stderr.strip()

def log(stdout, stderr):
    print(stdout.decode())

decorator = (
    CmdRunDecorator()
    .add_processor(validate, before=True)
    .add_processor(log, before=False)
)
```

### Modifiers

Modifiers transform the command data and return a new `(stdout, stderr)` pair.

```python
def to_upper(stdout, stderr):
    return stdout.upper(), stderr

def add_prefix(stdout, stderr):
    return b"Prefix: " + stdout, stderr
```

The evaluation order is:

    Pre-modifiers
         |
         v
    Pre-processors
         |
         v
    Command runner
         |
         v
    Post-modifiers
         |
         v
    Post-processors

This distinction is important:

- **Processors** observe or act on execution data.
- **Modifiers** transform execution data.

## Command execution integrations

The existing library provides several execution mechanisms.

### Local commands

Use `BashFactory` for local shell execution:

```python
from marsh.bash import BashFactory

bash = BashFactory()

command = bash.create_cmd_runner(
    'echo "Hello, $NAME"',
    env={"NAME": "World"},
)

stdout, stderr = command(b"", b"")
```

### SSH

Use `SshFactory` for SSH/Fabric-backed command execution:

```python
from marsh import Conveyor
from marsh.ssh import SshFactory

ssh = SshFactory(
    ("user@host:port",),
    {"connect_kwargs": {"password": "the_ssh_password"}},
)

command = ssh.create_cmd_runner("echo Hello, Remote World")

conveyor = Conveyor().add_cmd_runner(command)

stdout, stderr = conveyor()
```

Applications should use appropriate credential-management practices rather than embedding secrets directly in source code.

### Docker

Docker execution is available through the existing Docker executor APIs:

```python
from marsh.docker.docker_executor import DockerCommandExecutor

executor = DockerCommandExecutor("bash:latest", ...)

stdout, stderr = executor.run(
    b"",
    b"",
    environment={"MODE": "test"},
    workdir="/app",
)
```

### Python execution

Marsh also provides Python execution through `PythonExecutor`.

It supports both expression evaluation and statement execution:

```python
from marsh import PythonExecutor

executor = PythonExecutor(
    "x + y",
    mode="eval",
    namespace={"x": 1, "y": 2},
    use_pickle=False,
)

stdout, stderr = executor.run(b"", b"", ...)
```

These execution mechanisms remain part of Marsh's existing public API. The canonical Workflow API currently uses local process execution as its primary runtime path.

## DAG workflows

Marsh also provides a DAG API for dependency-based execution.

The DAG package includes:

- `Node`
- `Dag`
- `SyncDag`
- `AsyncDag`
- `ThreadDag`
- `ThreadPoolDag`
- `MultiprocessDag`
- `ProcessPoolDag`

A `Node` represents executable work, while a `Dag` represents relationships between executable objects.

```python
from marsh import Conveyor
from marsh.dag import Node, SyncDag

node_a = Node(
    "a",
    Conveyor().add_cmd_runner(cmd_a),
)

node_b = Node(
    "b",
    Conveyor().add_cmd_runner(cmd_b),
)

dag = SyncDag("example")
dag.do(node_a).then(node_b)

results = dag.start()
```

DAGs can also contain other startable objects, including nested DAGs.

### Multiprocessing

`MultiprocessDag` and `ProcessPoolDag` require the usual Python multiprocessing entry-point guard:

```python
if __name__ == "__main__":
    dag.start()
```

### DAG limitation

The existing DAG API currently provides dependency execution but does not provide general result/data passing between dependent tasks.

Applications requiring the canonical workflow semantics should prefer `Workflow` and `Task`.

## CLI inspection and extensions

Marsh now provides a read-only CLI boundary for inspecting canonical workflow
semantics without executing work:

    marsh inspect workflow.json
    marsh inspect workflow.json --json
    marsh plugins list
    marsh plugins list --json

Inspection reuses the canonical validation, planning, and identity APIs. It does
not execute a workflow or expose provider credentials. Machine-readable output is
deterministic JSON.

Optional integrations are discovered through the standard Python entry-point group
`marsh.extensions`. Discovery is deterministic and performs compatibility checks
before loading extension code. Extensions must declare the
`Marsh-Extension-Contract` metadata field. See
[the CLI reference](docs/reference/cli.md) and
[the extension reference](docs/reference/extensions.md).

## Architecture

For the implemented architecture and design boundaries, see [`docs/concepts/architecture.md`](docs/concepts/architecture.md).

## Current limitations

The current release line intentionally has several boundaries:

- The canonical runtime is local and sequential.
- General task-to-task result/data passing is not implemented yet.
- The canonical workflow API now has a read-only inspection CLI; it does not provide execution controls.
- YAML authoring is not currently provided.
- Callable operations are Python-specific and are not portable JSON definitions.
- Remote and container execution remain available through existing APIs rather than being part of the canonical local runtime.
- The project is still Alpha.

These limitations describe the current implementation; they should not be interpreted as permanent exclusions.


## Documentation

The documentation is organized for progressive discovery:

- [Documentation index](docs/README.md) — entry point and documentation map.
- [Workflow tutorial](docs/tutorials/workflow.md) — canonical Workflow API walkthrough.
- [Architecture](docs/concepts/architecture.md) — implemented architecture and design boundaries.
- [Semantic contract](docs/concepts/semantic-contracts.md) — canonical semantic ownership, lifecycle, identity, capability, recovery, and conformance rules.
- [Artifacts and reproducibility](docs/concepts/artifacts-and-reproducibility.md) — identity, artifacts, provenance, and integrity.
- [API migration](docs/how-to/migrate-api.md) — incremental migration from legacy APIs.
- [CLI reference](docs/reference/cli.md) — read-only inspection and extension discovery commands.
- [Extension reference](docs/reference/extensions.md) — extension metadata and compatibility rules.
- [Workflow IR reference](docs/reference/workflow-ir.md) — canonical `marsh.workflow/v1` representation.
- [Release history](docs/releases/) — version-specific release documentation.


## Development

Marsh uses `uv` for dependency and environment management.

Install all development and test dependencies:

```bash
uv sync --all-groups
```

Run tests:

```bash
uv run pytest -vv --disable-warnings --tb=short
```

Run linting:

```bash
uv run pflake8
```

Build the package:

```bash
uv build
```

Examples are available under [`samples/`](samples/).

## Compatibility

Marsh is evolving incrementally.

Existing public APIs including:

- `Conveyor`;
- command runners;
- processors and modifiers;
- executors;
- SSH and Docker integrations; and
- DAG classes

remain important compatibility surfaces.

New functionality should prefer the canonical workflow contracts and adapt existing mechanisms into them rather than introducing a separate execution model.

For migration examples and legacy/deprecation guidance, see [`docs/how-to/migrate-api.md`](docs/how-to/migrate-api.md).

## Contributing

Before making architectural or public-interface changes:

1. Understand the existing behavior.
2. Inspect the affected APIs and tests.
3. Define the intended behavior.
4. Add or update tests.
5. Implement the smallest compatible change.
6. Run targeted tests.
7. Run the broader test suite.
8. Review compatibility and documentation impact.

Keep the core small, composable, dependency-light, and independent of provider-specific mechanisms wherever practical.

## License

Marsh is released under the MIT License. See [`LICENSE`](LICENSE).
