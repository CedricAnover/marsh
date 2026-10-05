"""Provider discovery, configuration, and capability negotiation for Marsh."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol, runtime_checkable

from marsh.core.domain import Machine


class ProviderError(RuntimeError):
    """Base error for provider-boundary failures."""


class ProviderConfigurationError(ProviderError, ValueError):
    """Raised for invalid provider configuration."""


class ProviderUnavailableError(ProviderError):
    """Raised when a configured provider cannot be reached."""


class UnsupportedCapabilityError(ProviderError, ValueError):
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


@dataclass(frozen=True)
class CapabilityRequirement:
    """Provider-independent capability requirements for admission."""

    required: frozenset[str]

    def __init__(self, required: Iterable[str] = ()):
        normalized = frozenset(str(value).strip() for value in required)
        if "" in normalized:
            raise ValueError("capability requirements cannot contain empty names")
        object.__setattr__(self, "required", normalized)


@dataclass(frozen=True)
class CapabilityMatch:
    """Deterministic capability negotiation result."""

    provider: str
    required: frozenset[str]
    available: frozenset[str]
    missing: frozenset[str]

    @property
    def satisfied(self) -> bool:
        return not self.missing


@dataclass(frozen=True)
class ProviderConfig:
    """Provider selection/configuration without provider-specific semantics."""

    name: str
    options: Mapping[str, object]

    def __init__(self, name: str, options: Mapping[str, object] | None = None):
        normalized = name.strip()
        if not normalized:
            raise ProviderConfigurationError("provider name must be non-empty")
        object.__setattr__(self, "name", normalized)
        object.__setattr__(self, "options", dict(options or {}))


@runtime_checkable
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

    def create_machine(self, **kwargs) -> Machine:
        from marsh.core.runtime import LocalMachine

        if kwargs:
            raise ProviderConfigurationError(
                f"unsupported local provider options: {sorted(kwargs)}"
            )
        return LocalMachine()


class ProviderRegistry:
    """Deterministic named provider registry with capability negotiation."""

    def __init__(self, providers: Mapping[str, Provider] | None = None):
        self._providers: dict[str, Provider] = {}
        for name, provider in (providers or {}).items():
            self.register(name, provider)

    def register(self, name: str, provider: Provider) -> None:
        config_name = name.strip()
        if not config_name:
            raise ProviderConfigurationError("provider name must be non-empty")
        if config_name in self._providers:
            raise ProviderConfigurationError(
                f"provider {config_name!r} is already registered"
            )
        if not isinstance(provider, Provider):
            raise TypeError("provider does not satisfy the Provider contract")
        self._providers[config_name] = provider

    def get(self, name: str) -> Provider | None:
        return self._providers.get(name.strip())

    def find(self, capabilities: Iterable[str] = ()) -> tuple[tuple[str, Provider], ...]:
        required = frozenset(capabilities)
        return tuple(
            (name, self._providers[name])
            for name in sorted(self._providers)
            if self._providers[name].capabilities.satisfies(required)
        )

    def require(
        self,
        name: str,
        capabilities: Iterable[str] = (),
    ) -> Provider:
        provider = self.get(name)
        if provider is None:
            raise KeyError(name)
        required = frozenset(capabilities)
        if not provider.capabilities.satisfies(required):
            missing = sorted(required - provider.capabilities.values)
            raise UnsupportedCapabilityError(
                f"provider {name!r} does not support capabilities: {', '.join(missing)}"
            )
        return provider

    def negotiate(
        self,
        name: str,
        capabilities: Iterable[str] = (),
    ) -> CapabilityMatch:
        provider = self.get(name)
        required = CapabilityRequirement(capabilities).required
        available = (
            provider.capabilities.values if provider is not None else frozenset()
        )
        return CapabilityMatch(
            provider=name.strip(),
            required=required,
            available=frozenset(available),
            missing=frozenset(required - available),
        )

    def resolve(
        self,
        config: ProviderConfig,
        capabilities: Iterable[str] = (),
    ) -> Provider:
        match = self.negotiate(config.name, capabilities)
        provider = self.get(config.name)
        if provider is None:
            raise KeyError(config.name)
        if not match.satisfied:
            missing = sorted(match.missing)
            raise UnsupportedCapabilityError(
                f"provider {config.name!r} does not support capabilities: {', '.join(missing)}"
            )
        return provider
