# Remote execution boundary reference

v0.4.1 defines the semantic contracts needed to cross a process or machine
boundary without selecting a production transport.

## Contracts

### MachineConnection

`MachineConnection` owns transport/session concerns:

- `connect()`
- `disconnect()`
- `execute(request)`

It must not redefine workflow, scheduling, lifecycle, or policy semantics.

### ExecutionSubstrate

`ExecutionSubstrate` describes an execution environment through:

- `machine_id`;
- `capabilities`;
- an optional `connection`.

The identity is descriptive machine identity, not process identity.

### Agent

`Agent` is an optional machine-side endpoint implementing:

`execute(ExecutionRequest) -> ExecutionResponse`

It is not a scheduler, cluster manager, or Marsh server.

### ExecutionRequest

The request carries:

- `execution_id`;
- `attempt_id`;
- `task_id`;
- `ProcessSpec`.

Execution and attempt identities are explicit because provider-local handles
and PIDs are not portable semantic identities.

### ExecutionResponse

The response carries execution/attempt identity and the observed `ProcessStatus`.
A concrete transport may additionally attach a structured `Result`.

## Reconciliation

`reconcile_remote_result()` follows a conservative rule:

1. if an authoritative result is available and its identity matches, use it;
2. if the identity does not match, reject the evidence;
3. if a transport failure occurs without authoritative result evidence, raise an
   ambiguous `RemoteExecutionError`;
4. never infer success or failure solely from loss of connectivity.

## Reference transport

`SocketMachineConnection` is a deliberately small standard-library TCP adapter.
It exists to prove that requests and responses can cross a real process/network
boundary. It is not a production transport commitment.

Future transports must preserve the same semantic contract and remain replaceable
behind `MachineConnection`.

## Conformance expectations

A connection/provider implementation should test:

- identity preservation;
- lifecycle/result preservation;
- capability mismatches;
- timeout/cancellation behavior;
- transport interruption;
- duplicate or mismatched observations;
- cleanup;
- cross-process serialization;
- relevant cross-OS behavior;
- sensitive-data handling.
