# Resources

Resources are independently identifiable, lifecycle-bearing infrastructure capabilities. They are semantic objects used for planning and composition; provider-specific mechanisms remain behind adapters.

## Identity

`ResourceIdentity(kind, name)` is the stable semantic identity. The identity is independent of provider-local handles, process IDs, container IDs, filesystem paths, memory addresses, and unstable representations.

```python
from marsh import ResourceIdentity

identity = ResourceIdentity("machine", "build")
assert identity.value == "machine:build"
```

## Lifecycle

The canonical lifecycle is:

```text
DECLARED -> VALIDATED -> NEGOTIATED -> SELECTED -> PLANNED
    -> CREATING -> REALIZED -> ACTIVE -> RELEASING -> RELEASED
                         \-> RECOVERING -> REALIZED / RELEASED
                                      \-> UNKNOWN / AMBIGUOUS
```

Recovery is evidence-driven. Marsh does not infer a successful create/release after an interrupted operation. `UNKNOWN` or `AMBIGUOUS` is preserved when authoritative postcondition evidence is unavailable.

## ResourceGraph

`ResourceGraph` stores resources by identity and deterministic dependency relationships. It rejects duplicate identities and references to resources that have not been added. Inspection is stable because identities and relationships are returned in sorted order.

The graph intentionally does not define network, storage, virtualization, or other future-domain topology semantics. Those domains remain provider/adapter concerns until their roadmap releases define them.

## Provider boundary

The existing `Provider` contract remains valid. Providers that also materialize resources can opt into the structural `ResourceProvider` contract:

```text
Provider
  + capabilities
  + create_machine(...)

ResourceProvider (optional)
  + resource_capabilities
  + create_resource(identity, ...)
```

This preserves backward compatibility: a provider does not become invalid merely because it does not implement resource creation.

## Heterogeneous adapters

The reference implementation demonstrates two different domains without adding a universal resource framework:

- machine resources, materialized by the existing local/Docker provider boundary;
- artifact-store resources, exposed through `ArtifactStoreResourceAdapter` over the existing `ArtifactStore` abstraction.

Both use the same identity, lifecycle, and graph semantics. Their provider-specific configuration and mechanisms remain outside the semantic kernel.
