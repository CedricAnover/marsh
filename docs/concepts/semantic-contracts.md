# Semantic contract

This document is the implementation contract for the Stable Workflow Kernel. It freezes semantic ownership before remote execution work.

## Canonical ownership

| Concept | Canonical owner | Boundary rule |
| --- | --- | --- |
| Workflow | `Workflow` | Defines the provider-independent unit of work. |
| Task | `Task` | Defines one unit of work plus dependency relationships. |
| Process description | `ProcessSpec` | Describes process intent; it never represents an observed process instance. |
| Execution identity | `execution_id()` | Identifies semantic workflow execution independently of PID/provider handles. |
| Attempt identity | Result metadata / runtime policy | Identifies an individual attempt; retries do not create a new semantic execution. |
| Process lifecycle | `ProcessStatus` + transition rules | Provider mechanisms are normalized into canonical lifecycle semantics. |
| Result | `Result` | Represents semantic outcome; stderr alone is not failure. |
| Artifact | `Artifact` / `ArtifactStore` | Durable payload/integrity boundary; artifacts do not redefine execution outcomes. |
| Provider | `Provider` / `ProviderRegistry` | Supplies mechanisms/capabilities; it does not define workflow semantics. |
| Scheduler | `Scheduler` | Determines readiness/order; it does not own process/provider semantics. |
| Diagnostics | diagnostic/redaction boundaries | Projects canonical state and remains secret-safe. |
| Inspection | CLI inspection boundary | Read-only projection; inspection never executes or mutates workflow state. |

## Lifecycle contract

The current stable lifecycle is `created -> starting -> running -> stopping -> terminal`.

Current terminal outcomes are:

- `completed`
- `failed`
- `cancelled`
- `timed_out`
- `skipped`
- `blocked`

The kernel adds explicit `unknown` and `ambiguous` observation states. They are unresolved states, not proof of success or failure, and therefore are not treated as terminal lifecycle completion. An infrastructure/provider error is not, by itself, proof that work did not complete.

Non-negotiable invariants:

1. Terminal states cannot transition back into active states.
2. Timeout, cancellation, and failure remain distinct outcomes.
3. A cancellation request is not the same thing as confirmed cancellation.
4. Recovery may resolve uncertainty only after independently verifying its postcondition.
5. Unknown/ambiguous state remains visible until authoritative evidence resolves it.

## Identity contract

Semantic identity must not depend on PID/thread ID, container/runtime-local IDs, provider handles, object memory addresses, local filesystem paths, or unstable `repr()` output.

Workflow execution identity is derived from canonical semantic workflow data plus explicitly supplied semantic inputs/policy. Attempt identity varies across retries while execution identity remains stable.

## Capability contract

Capabilities describe what a mechanism can do, not what the workflow means.

Requirements are evaluated before provider-specific behavior where possible. Missing capability produces an explicit deterministic mismatch and does not mutate canonical workflow state.

Stable seams:

- Machine — materializes processes.
- Process Observation — observes process state.
- Process Control — requests lifecycle actions.
- Workspace — names filesystem/workspace boundary.
- Resource Observation — reports available resources.
- Resource Policy — declares requirements.
- Isolation — describes execution isolation capabilities.

These are semantic contracts, not commitments to psutil, PyFilesystem2, containers, SSH, gRPC, or another implementation library.

## Recovery contract

All infrastructure recovery follows:

`intent -> operation -> observed error/interruption -> verification query -> postcondition -> final classification`

Rules:

- verified postcondition => classify from verified state;
- insufficient evidence => remain UNKNOWN/AMBIGUOUS;
- recovery is bounded and idempotent where applicable;
- recovery must not fabricate success or failure;
- platform-specific races stay at infrastructure boundaries.

## Conformance contract

Provider, scheduler, artifact, and inspection implementations are evaluated against the same semantic fixture.

Minimum negative-path coverage includes timeout, cancellation, cleanup failure, provider exception, unsupported capability, invalid requirement, duplicate/late observation, partial failure, cross-process reconstruction, and relevant cross-OS behavior.

The kernel remains standard-library-first. Optional infrastructure dependencies belong behind explicit provider/adapter boundaries.

## Non-goals

- remote transport implementation;
- distributed control plane;
- gRPC/Protocol Buffers commitment;
- second runtime or scheduler;
- provider-specific semantic branches in core;
- mandatory new runtime dependencies;
- generalized persistence/event sourcing.

## Remote execution boundary

Remote execution may define and implement the minimum remote transport boundary only after these semantics are executable and conformance-tested. Remote execution must preserve the same identity, lifecycle, ambiguity, cancellation, artifact, and reconciliation vocabulary rather than redefine it.
