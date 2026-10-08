"""Provider-independent resource identity, lifecycle, and graph contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable


class ResourceState(str, Enum):
    DECLARED = "declared"
    VALIDATED = "validated"
    NEGOTIATED = "negotiated"
    SELECTED = "selected"
    PLANNED = "planned"
    CREATING = "creating"
    REALIZED = "realized"
    ACTIVE = "active"
    RELEASING = "releasing"
    RELEASED = "released"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"


_RESOURCE_TRANSITIONS = {
    ResourceState.DECLARED: frozenset({ResourceState.VALIDATED}),
    ResourceState.VALIDATED: frozenset({ResourceState.NEGOTIATED}),
    ResourceState.NEGOTIATED: frozenset({ResourceState.SELECTED}),
    ResourceState.SELECTED: frozenset({ResourceState.PLANNED}),
    ResourceState.PLANNED: frozenset({ResourceState.CREATING}),
    ResourceState.CREATING: frozenset(
        {ResourceState.REALIZED, ResourceState.RECOVERING}
    ),
    ResourceState.REALIZED: frozenset({ResourceState.ACTIVE, ResourceState.RELEASING}),
    ResourceState.ACTIVE: frozenset({ResourceState.RELEASING}),
    ResourceState.RELEASING: frozenset(
        {ResourceState.RELEASED, ResourceState.RECOVERING}
    ),
    ResourceState.RECOVERING: frozenset(
        {
            ResourceState.REALIZED,
            ResourceState.RELEASED,
            ResourceState.UNKNOWN,
            ResourceState.AMBIGUOUS,
        }
    ),
}


def can_transition_resource(current: ResourceState, target: ResourceState) -> bool:
    """Return whether a resource lifecycle transition is explicitly supported."""
    return target in _RESOURCE_TRANSITIONS.get(current, frozenset())


@dataclass(frozen=True, order=True)
class ResourceIdentity:
    """Stable semantic identity independent of provider-local handles."""

    kind: str
    name: str

    def __post_init__(self) -> None:
        kind = self.kind.strip()
        name = self.name.strip()
        if not kind or not name:
            raise ValueError("resource identity kind and name must be non-empty")
        if ":" in kind:
            raise ValueError("resource identity kind cannot contain ':'")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "name", name)

    @property
    def value(self) -> str:
        return f"{self.kind}:{self.name}"


@runtime_checkable
class ResourceProtocol(Protocol):
    """Small structural contract shared by resource implementations."""

    @property
    def identity(self) -> ResourceIdentity: ...

    @property
    def state(self) -> ResourceState: ...


@dataclass
class Resource:
    """Reference resource carrying semantic identity and lifecycle evidence."""

    identity: ResourceIdentity
    state: ResourceState = ResourceState.DECLARED
    metadata: Mapping[str, Any] = field(default_factory=dict)
    state_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ResourceIdentity):
            raise TypeError("resource identity must be a ResourceIdentity")
        self.metadata = dict(self.metadata)

    def transition(self, target: ResourceState) -> None:
        if not can_transition_resource(self.state, target):
            raise ValueError(
                f"invalid resource transition: {self.state.value} -> {target.value}"
            )
        self.state = target
        self.state_reason = None

    def mark_unknown(self, reason: str) -> None:
        if not reason or not reason.strip():
            raise ValueError("resource state reason must be non-empty")
        if self.state not in {ResourceState.RECOVERING}:
            raise ValueError("unknown resource state requires recovery")
        self.state = ResourceState.UNKNOWN
        self.state_reason = reason.strip()

    def mark_ambiguous(self, reason: str) -> None:
        if not reason or not reason.strip():
            raise ValueError("resource state reason must be non-empty")
        if self.state is not ResourceState.RECOVERING:
            raise ValueError("ambiguous resource state requires recovery")
        self.state = ResourceState.AMBIGUOUS
        self.state_reason = reason.strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identity.value,
            "kind": self.identity.kind,
            "name": self.identity.name,
            "state": self.state.value,
            "metadata": dict(self.metadata),
            "state_reason": self.state_reason,
        }


class ArtifactStoreResourceAdapter:
    """Adapter that exposes an ArtifactStore as a lifecycle-bearing resource."""

    def __init__(self, name: str, store: Any):
        self.resource = Resource(ResourceIdentity("artifact-store", name))
        self.store = store

    @property
    def identity(self) -> ResourceIdentity:
        return self.resource.identity

    @property
    def state(self) -> ResourceState:
        return self.resource.state

    def validate(self) -> Resource:
        self.resource.transition(ResourceState.VALIDATED)
        return self.resource

    def realize(self) -> Resource:
        if self.resource.state is ResourceState.VALIDATED:
            self.resource.transition(ResourceState.NEGOTIATED)
            self.resource.transition(ResourceState.SELECTED)
            self.resource.transition(ResourceState.PLANNED)
        self.resource.transition(ResourceState.CREATING)
        self.resource.transition(ResourceState.REALIZED)
        self.resource.transition(ResourceState.ACTIVE)
        return self.resource

    def release(self) -> Resource:
        self.resource.transition(ResourceState.RELEASING)
        self.resource.transition(ResourceState.RELEASED)
        return self.resource


@dataclass
class ResourceGraph:
    """Deterministic resource identity and relationship graph."""

    _resources: dict[ResourceIdentity, Resource] = field(default_factory=dict)
    _dependencies: dict[ResourceIdentity, set[ResourceIdentity]] = field(
        default_factory=dict
    )

    def add(
        self,
        resource: ResourceProtocol,
        *,
        depends_on: tuple[ResourceIdentity, ...] = (),
    ) -> None:
        identity = resource.identity
        if identity in self._resources:
            raise ValueError(f"resource {identity.value!r} already exists")
        for dependency in depends_on:
            if dependency not in self._resources:
                raise KeyError(dependency)
            if dependency == identity:
                raise ValueError("resource cannot depend on itself")
        self._resources[identity] = resource  # type: ignore[assignment]
        self._dependencies[identity] = set(depends_on)

    def get(self, identity: ResourceIdentity) -> ResourceProtocol:
        return self._resources[identity]

    def identities(self) -> tuple[ResourceIdentity, ...]:
        return tuple(sorted(self._resources))

    def dependencies_of(
        self, identity: ResourceIdentity
    ) -> tuple[ResourceIdentity, ...]:
        if identity not in self._resources:
            raise KeyError(identity)
        return tuple(sorted(self._dependencies[identity]))

    def dependents_of(self, identity: ResourceIdentity) -> tuple[ResourceIdentity, ...]:
        if identity not in self._resources:
            raise KeyError(identity)
        return tuple(
            sorted(
                candidate
                for candidate, deps in self._dependencies.items()
                if identity in deps
            )
        )

    @staticmethod
    def _serialize_resource(resource: ResourceProtocol) -> dict[str, Any]:
        serializer = getattr(resource, "to_dict", None)
        if serializer is not None:
            data = dict(serializer())
        else:
            data = {
                "id": resource.identity.value,
                "kind": resource.identity.kind,
                "name": resource.identity.name,
                "state": resource.state.value,
                "metadata": dict(getattr(resource, "metadata", {})),
                "state_reason": getattr(resource, "state_reason", None),
            }
        return data

    def to_dict(self) -> dict[str, Any]:
        return {
            "resources": [
                {
                    **self._serialize_resource(self._resources[identity]),
                    "depends_on": [
                        dependency.value
                        for dependency in self.dependencies_of(identity)
                    ],
                }
                for identity in self.identities()
            ]
        }


__all__ = [
    "Resource",
    "ArtifactStoreResourceAdapter",
    "ResourceGraph",
    "ResourceIdentity",
    "ResourceProtocol",
    "ResourceState",
    "can_transition_resource",
]
