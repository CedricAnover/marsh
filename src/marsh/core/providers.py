"""Provider discovery and capability negotiation for Marsh."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol

from marsh.core.domain import Machine, ProcessSpec
from marsh.core.runtime import LocalMachine


class UnsupportedCapabilityError(ValueError):
    """Raised when a provider cannot satisfy a required capability."""


@dataclass(frozen=True)
class ProviderCapabilities:
    """Immutable set of capabilities exposed by an execution provider."""

    values: frozenset[str]

    def __init__(self, values: Iterable[str]):
        normalized = frozenset(str(value).strip() for value in values)
        if "" in normalized:
            raise ValueError("provider capabilities cannot contain empty names")
        object.__setattr__(self, "values", normalized)

    def __contains__(self, capability: str) -> bool:
        return capability in self.values

    def __iter__(self):
        return iter(sorted(self.values))

    def satisfies(self, required: Iterable[str]) -> bool:
        return set(required).issubset(self.values)


class Provider(Protocol):
    """Mechanism boundary for materializing execution machines."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        ...

    def create_machine(self, **kwargs) -> Machine:
        ...


class LocalProvider:
    """Reference provider for the existing local process mechanism."""

    name = "local"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            {
                "machine.create",
                "process.start",
                "process.wait",
                "process.poll",
                "process.stop",
                "process.terminate",
                "process.kill",
                "process.cancel",
                "process.result",
            }
        )

    def create_machine(self, **kwargs) -> LocalMachine:
        if kwargs:
            raise TypeError(f"unsupported local provider options: {sorted(kwargs)}")
        return LocalMachine()


class ProviderRegistry:
    """Named provider registry with explicit capability negotiation."""

    def __init__(self, providers: Mapping[str, Provider] | None = None):
        self._providers: dict[str, Provider] = {}
        for name, provider in (providers or {}).items():
            self.register(name, provider)

    def register(self, name: str, provider: Provider) -> None:
        name = name.strip()
        if not name:
            raise ValueError("provider name must be non-empty")
        if name in self._providers:
            raise ValueError(f"provider {name!r} is already registered")
        self._providers[name] = provider

    def get(self, name: str) -> Provider | None:
        return self._providers.get(name)

    def require(self, name: str, capabilities: Iterable[str] = ()) -> Provider:
        provider = self._providers.get(name)
        if provider is None:
            raise KeyError(name)
        required = frozenset(capabilities)
        if not provider.capabilities.satisfies(required):
            missing = sorted(required - provider.capabilities.values)
            raise UnsupportedCapabilityError(
                f"provider {name!r} does not support capabilities: {', '.join(missing)}"
            )
        return provider
