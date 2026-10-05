# Workflow IR

Marsh establishes the versioned `marsh.workflow/v1` canonical Workflow IR.

## Boundary

```text
Authoring -> Configuration -> Canonical Workflow IR -> deterministic JSON
                                      |
                                      v
                              Reconstruction
                                      |
                                      v
                              Existing Runtime
```

The package version and IR schema version are intentionally independent. The document envelope is:

```text
WorkflowDocument
+- schema
|  +- name = marsh.workflow
|  +- version = 1
+- workflow
|  +- id
|  +- tasks[]
|  +- inputs
|  +- outputs
|  +- metadata
+- extensions
```

Workflow and task identifiers are semantic identities. They are never derived from object addresses, PIDs, thread IDs, memory addresses, local paths, or callable representations.

## Operations

Importable top-level Python callables are represented explicitly:

```json
{"kind":"python_callable","module":"package.tasks","qualname":"build"}
```

Lambdas, local functions, and `__main__` callables are rejected. Reconstruction uses `importlib.import_module()` and qualified attribute traversal; serialized Python source is never evaluated.

Process operations use structured `ProcessSpec` data. The v1 value contract accepts null, booleans, integers, finite numbers, strings, arrays, and string-keyed objects. Bytes and arbitrary runtime objects are rejected rather than silently encoded.

## Configuration

Configuration remains separate from runtime domain objects. Marsh adds provider-neutral Machine, Scheduler, Policy, and Provider configuration families.

Pydantic 2.x was evaluated as a boundary-validation dependency but is not required: the existing dependency-free dataclass boundary is sufficiently small, explicit, and testable, while adding Pydantic would increase the minimal core dependency surface without removing a current semantic responsibility.

## Determinism and compatibility

Canonical JSON uses stable task ordering, recursively normalized mappings, string object keys, compact separators, and `allow_nan=False`.

The existing `workflow_to_*()` APIs now emit/read the canonical v1 envelope, while `workflow_from_dict()` and `workflow_from_json()` continue to accept legacy data-oriented authoring inputs when no schema envelope is present.

Unknown schema versions fail explicitly. Reconstruction does not require the original live Python object graph for supported operations.
