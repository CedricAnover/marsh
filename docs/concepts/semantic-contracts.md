# Semantic contract

This document is the implementation contract for the v0.4.0 Stable Workflow Kernel. It freezes semantic ownership before v0.4.1 remote execution work.

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

v0.4.0 adds explicit `unknown` and `ambiguous` observation states. They are unresolved states, not proof of success or failure, and therefore are not treated as terminal lifecycle completion. An infrastructure/provider error is not, by itself, proof that work did not complete.

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

## Remote boundary

v0.4.1 implements the minimum transport-neutral remote boundary:

- `MachineConnection` owns connection/session mechanics;
- `ExecutionSubstrate` describes machine-side execution capability;
- `Agent` is an optional machine-side execution endpoint;
- `ExecutionRequest` and `ExecutionResponse` preserve execution and attempt identity;
- `reconcile_remote_result()` refuses to infer failure or success from a transport interruption alone.

The reference `SocketMachineConnection` uses standard-library TCP/JSON framing for conformance evidence only. It is not a production transport commitment.

Remote execution must preserve the same identity, lifecycle, ambiguity, cancellation, artifact, and reconciliation vocabulary rather than redefine it.

## Capability discovery and negotiation

Provider capability discovery is observational and normalized before admission or dispatch. A discovery result has one of four states:

- **supported** — authoritative discovery reports a capability set;
- **unsupported** — authoritative discovery completed, but one or more requested capabilities are missing;
- **unavailable** — the provider cannot currently be queried or is not registered;
- **indeterminate** — discovery failed without enough evidence to establish support or lack of support.

`ProviderRegistry.negotiate()` returns a deterministic `CapabilityMatch` containing the normalized requirement, advertised capabilities, missing capabilities, state, and optional reason. Unsupported requirements are rejected before provider dispatch when authoritative information exists. Unavailable or indeterminate discovery never fabricates support.

Legacy providers exposing only `capabilities` remain compatible; the registry normalizes that static declaration as a supported discovery result. Provider-specific discovery mechanisms stay behind the provider boundary.


## Provider/adapter hardening

v0.4.2 makes the capability and provider boundary implementation-backed across the supported provider surface.

- CapabilityState distinguishes supported, unsupported, unavailable, and indeterminate discovery.
- CapabilityDiscovery normalizes provider-specific discovery into a provider-neutral observation.
- CapabilityMatch provides deterministic admission evidence: required, available, missing, state, and reason.
- Unsupported requirements are rejected before provider dispatch when authoritative capability information exists.
- Unavailable or indeterminate discovery never fabricates support.
- Legacy providers that expose only static capabilities remain compatible.
- Docker capability discovery reports unavailable when the optional Docker dependency is missing rather than making core imports depend on Docker.
- Heterogeneous Local/Docker conformance covers capability admission, optional-dependency absence, provider exceptions, and real Docker integration.
- Partial provider failure remains adapter-owned and uses the existing bounded postcondition-based recovery primitive; unresolved state remains ambiguous.
- Provider handles and provider-specific configuration remain opaque to canonical capability serialization and semantic identity.

The v0.4.2 boundary remains standard-library-first: Docker and Fabric remain optional integrations, and no production distributed transport or second runtime/scheduler is introduced.
