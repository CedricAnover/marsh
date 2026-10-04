# Marsh Architecture

## Architecture

Marsh is moving toward a small execution kernel with explicit boundaries:

```mermaid
flowchart TD
    A[UX / Python API] --> B[Workflow / Task]
    B --> C[Validation]
    C --> D[Planning]
    D --> E[Scheduler]
    E --> F[Machine / Process]
    F --> G[Result]
```

The architectural goal is to keep:

- workflow intent;
- execution mechanisms;
- machines;
- processes;
- scheduling;
- policies;
- providers;
- observability; and
- results

as distinct concepts.

The existing command and DAG APIs remain useful low-level building blocks and compatibility surfaces.

## Implementation status

This document describes the architecture implemented by the current Alpha release. Future capabilities are described only as extension boundaries and are not presented as implemented features.

### Scheduler state machine (v0.3.5)

The canonical runtime now uses one shared scheduler state model across sequential and bounded-concurrency modes:

```text
READY -> RUNNING -> SUCCEEDED
                 -> FAILED
                 -> CANCELLED
READY -> BLOCKED
```

Dependency readiness is defined by `all(dependency == SUCCEEDED)`. Failed, cancelled, or blocked dependencies prevent downstream dispatch. Concurrent modes use a deterministic ready ordering and a hard `max_concurrency` bound.

The scheduler owns readiness and dispatch policy; Machine/Process/Provider components own execution. Process-mode execution crosses the process boundary only with serializable task state, dependency results, and a picklable execution callback.

```text
Workflow
  |
  v
Validation / graphlib planning
  |
  v
Scheduler state machine
  |---- READY tasks ----> bounded dispatch ----> execution
  |                                             |
  +<------------- Result / state ---------------+
```



## Provider boundary (v0.3.4)

Providers are execution-mechanism adapters. Workflow intent, planning, scheduling, and policy semantics remain provider-independent.

```mermaid
classDiagram
    Workflow --> ExecutionPlan
    ExecutionPlan --> Scheduler
    Scheduler --> Machine
    Machine --> Process
    Process --> Result
    Workflow --> ProviderRegistry
    ProviderRegistry --> Provider
    ProviderConfig --> ProviderRegistry
    Provider --> Machine
    Provider --> Result

    class Provider {
        <<protocol>>
        +capabilities
        +create_machine()
    }
    class ProviderConfig {
        +name
        +options
    }
    class ProviderRegistry {
        +register()
        +resolve()
        +find()
    }
    class LocalProvider
    class DockerProvider
    Provider <|.. LocalProvider
    Provider <|.. DockerProvider
```

Runtime resolution is deliberately outside the Workflow IR:

```text
execute_workflow(workflow, provider=config)
    -> resolve config.name in ProviderRegistry
    -> verify required capabilities
    -> materialize Provider Machine
    -> run the existing Scheduler
    -> return the existing Result model
```

A new backend should therefore add a Provider/Adapter and conformance tests rather than introduce provider-specific branching into Workflow or planning.
