from dataclasses import dataclass
from enum import Enum

import pytest

from marsh.core.resources import (
    Resource,
    ResourceGraph,
    ResourceIdentity,
    ResourceProtocol,
    ResourceState,
    can_transition_resource,
)


def test_resource_identity_is_stable_and_provider_handle_independent():
    identity = ResourceIdentity(kind="machine", name="build-host")
    assert identity.value == "machine:build-host"
    assert identity == ResourceIdentity(kind="machine", name="build-host")

    with pytest.raises(ValueError):
        ResourceIdentity(kind="", name="build-host")


def test_resource_lifecycle_is_explicit_and_bounded():
    resource = Resource(ResourceIdentity("machine", "build-host"))
    assert resource.state is ResourceState.DECLARED
    for state in (
        ResourceState.VALIDATED,
        ResourceState.NEGOTIATED,
        ResourceState.SELECTED,
        ResourceState.PLANNED,
        ResourceState.CREATING,
        ResourceState.REALIZED,
        ResourceState.ACTIVE,
        ResourceState.RELEASING,
        ResourceState.RELEASED,
    ):
        resource.transition(state)
    assert resource.state is ResourceState.RELEASED


def test_resource_recovery_never_guesses_unknown_state():
    resource = Resource(ResourceIdentity("artifact-store", "results"))
    for state in (
        ResourceState.VALIDATED,
        ResourceState.NEGOTIATED,
        ResourceState.SELECTED,
        ResourceState.PLANNED,
        ResourceState.CREATING,
    ):
        resource.transition(state)
    resource.transition(ResourceState.RECOVERING)
    resource.mark_unknown("provider lost authoritative state")
    assert resource.state is ResourceState.UNKNOWN
    assert resource.state_reason == "provider lost authoritative state"

    with pytest.raises(ValueError):
        resource.transition(ResourceState.ACTIVE)


def test_resource_graph_enforces_unique_identity_and_relationships():
    graph = ResourceGraph()
    machine = Resource(ResourceIdentity("machine", "build"))
    store = Resource(ResourceIdentity("artifact-store", "results"))
    graph.add(machine)
    graph.add(store, depends_on=(machine.identity,))

    assert graph.get(machine.identity) is machine
    assert graph.dependencies_of(store.identity) == (machine.identity,)
    assert graph.dependents_of(machine.identity) == (store.identity,)
    assert graph.identities() == (store.identity, machine.identity)

    with pytest.raises(ValueError, match="already exists"):
        graph.add(Resource(ResourceIdentity("machine", "build")))

    with pytest.raises(KeyError):
        graph.add(
            Resource(ResourceIdentity("artifact", "missing")),
            depends_on=(ResourceIdentity("x", "y"),),
        )


def test_resource_graph_serialization_is_deterministic():
    graph = ResourceGraph()
    graph.add(Resource(ResourceIdentity("z", "two")))
    graph.add(Resource(ResourceIdentity("a", "one")))
    first = graph.to_dict()
    second = graph.to_dict()
    assert first == second
    assert [item["id"] for item in first["resources"]] == ["a:one", "z:two"]


def test_resource_protocol_is_small_and_structural():
    @dataclass
    class ForeignResource:
        identity: ResourceIdentity
        state: ResourceState = ResourceState.ACTIVE

    assert isinstance(
        ForeignResource(ResourceIdentity("foreign", "one")), ResourceProtocol
    )


def test_resource_transition_table_rejects_terminal_reactivation():
    assert not can_transition_resource(ResourceState.RELEASED, ResourceState.ACTIVE)
    assert can_transition_resource(ResourceState.CREATING, ResourceState.REALIZED)
    assert can_transition_resource(ResourceState.CREATING, ResourceState.RECOVERING)
    assert can_transition_resource(ResourceState.RECOVERING, ResourceState.UNKNOWN)


def test_local_provider_exposes_resource_capability_without_changing_process_provider_contract():
    from marsh.core.providers import LocalProvider, ResourceProvider

    provider = LocalProvider()
    assert isinstance(provider, ResourceProvider)
    resource = provider.create_resource(ResourceIdentity("machine", "build"))
    assert resource.identity.value == "machine:build"
    assert resource.state is ResourceState.ACTIVE


def test_artifact_store_adapter_is_second_heterogeneous_resource_domain(tmp_path):
    from marsh.core.artifact_store import LocalArtifactStore
    from marsh.core.resources import ArtifactStoreResourceAdapter

    adapter = ArtifactStoreResourceAdapter("results", LocalArtifactStore(tmp_path))
    resource = adapter.validate()
    assert resource.identity.kind == "artifact-store"
    adapter.realize()
    assert adapter.state is ResourceState.ACTIVE
    adapter.release()
    assert adapter.state is ResourceState.RELEASED
