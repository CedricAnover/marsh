"""Provider discovery, configuration, and capability negotiation for Marsh."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable

from marsh.core.domain import Machine


class ProviderError(RuntimeError):
    """Base error for provider-boundary failures."""


class ProviderConfigurationError(ProviderError, ValueError):
    """Raised for invalid provider configuration."""


class ProviderUnavailableError(ProviderError):
    """Raised when a configured provider cannot be reached."""


class UnsupportedCapabilityError(ProviderError, ValueError):
    """Raised when a provider cannot satisfy a required capability."""


class CapabilityState(str, Enum):
    """Authoritative state of provider capability discovery."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    INDETERMINATE = "indeterminate"


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
class CapabilityDiscovery:
    """Normalized, observational provider capability discovery result."""

    state: CapabilityState
    capabilities: ProviderCapabilities
    reason: str | None = None

    @classmethod
    def supported(cls, capabilities: Iterable[str]) -> "CapabilityDiscovery":
        return cls(CapabilityState.SUPPORTED, ProviderCapabilities(capabilities))

    @classmethod
    def unsupported(
        cls, capabilities: Iterable[str], reason: str | None = None
    ) -> "CapabilityDiscovery":
        return cls(
            CapabilityState.UNSUPPORTED,
            ProviderCapabilities(capabilities),
            reason,
        )

    @classmethod
    def unavailable(cls, reason: str | None = None) -> "CapabilityDiscovery":
        return cls(CapabilityState.UNAVAILABLE, ProviderCapabilities(()), reason)

    @classmethod
    def indeterminate(cls, reason: str | None = None) -> "CapabilityDiscovery":
        return cls(CapabilityState.INDETERMINATE, ProviderCapabilities(()), reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "capabilities": tuple(self.capabilities),
            "reason": self.reason,
        }


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
    state: CapabilityState
    reason: str | None = None

    @property
    def satisfied(self) -> bool:
        return self.state is CapabilityState.SUPPORTED and not self.missing

    @property
    def admissible(self) -> bool:
        """Return whether authoritative discovery permits provider dispatch."""
        return self.satisfied

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "required": tuple(sorted(self.required)),
            "available": tuple(sorted(self.available)),
            "missing": tuple(sorted(self.missing)),
            "state": self.state.value,
            "reason": self.reason,
            "satisfied": self.satisfied,
        }


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

    def discover_capabilities(self) -> CapabilityDiscovery:
        return CapabilityDiscovery.supported(self.capabilities)

    def create_machine(self, **kwargs) -> Machine:
        from marsh.core.runtime import LocalMachine

        if kwargs:
            raise ProviderConfigurationError(
                f"unsupported local provider options: {sorted(kwargs)}"
            )
        return LocalMachine()


def _discover(provider: Provider) -> CapabilityDiscovery:
    """Normalize legacy and explicit provider capability discovery."""
    discover = getattr(provider, "discover_capabilities", None)
    if discover is None:
        return CapabilityDiscovery.supported(provider.capabilities)

    try:
        result = discover()
    except ProviderUnavailableError as exc:
        return CapabilityDiscovery.unavailable(str(exc))
    except Exception as exc:
        return CapabilityDiscovery.indeterminate(str(exc))

    if isinstance(result, CapabilityDiscovery):
        return result
    if isinstance(result, ProviderCapabilities):
        return CapabilityDiscovery.supported(result.values)
    if isinstance(result, Iterable) and not isinstance(result, (str, bytes)):
        return CapabilityDiscovery.supported(result)
    raise TypeError("provider capability discovery returned an unsupported value")


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

    def discover(self, name: str) -> CapabilityDiscovery:
        provider = self.get(name)
        if provider is None:
            return CapabilityDiscovery.unavailable("provider is not registered")
        return _discover(provider)

    def find(self, capabilities: Iterable[str] = ()) -> tuple[tuple[str, Provider], ...]:
        required = frozenset(capabilities)
        return tuple(
            (name, self._providers[name])
            for name in sorted(self._providers)
            if self.negotiate(name, required).satisfied
        )

    def require(
        self,
        name: str,
        capabilities: Iterable[str] = (),
    ) -> Provider:
        match = self.negotiate(name, capabilities)
        provider = self.get(name)
        if provider is None:
            raise KeyError(name)
        if match.state is CapabilityState.UNAVAILABLE:
            raise ProviderUnavailableError(
                match.reason or f"provider {name!r} is unavailable"
            )
        if match.state is not CapabilityState.SUPPORTED or match.missing:
            missing = sorted(match.missing)
            suffix = f": {', '.join(missing)}" if missing else ""
            raise UnsupportedCapabilityError(
                f"provider {name!r} cannot satisfy capabilities{suffix}"
            )
        return provider

    def negotiate(
        self,
        name: str,
        capabilities: Iterable[str] = (),
    ) -> CapabilityMatch:
        provider_name = name.strip()
        required = CapabilityRequirement(capabilities).required
        discovery = self.discover(provider_name)
        missing = frozenset(required - discovery.capabilities.values)
        state = discovery.state
        if state is CapabilityState.SUPPORTED and missing:
            state = CapabilityState.UNSUPPORTED
        return CapabilityMatch(
            provider=provider_name,
            required=required,
            available=discovery.capabilities.values,
            missing=missing,
            state=state,
            reason=discovery.reason,
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
        if match.state is CapabilityState.UNAVAILABLE:
            raise ProviderUnavailableError(
                match.reason or f"provider {config.name!r} is unavailable"
            )
        if not match.satisfied:
            missing = sorted(match.missing)
            suffix = f": {', '.join(missing)}" if missing else ""
            raise UnsupportedCapabilityError(
                f"provider {config.name!r} cannot satisfy capabilities{suffix}"
            )
        return provider
