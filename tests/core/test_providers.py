import pytest

from marsh.core.domain import ProcessSpec, ProcessStatus, Result, Workflow, Task
from marsh.core.policies import FailurePolicy, ResourcePolicy, RetryPolicy, TimeoutPolicy
from marsh.core.providers import (
    CapabilityDiscovery,
    CapabilityState,
    LocalProvider,
    ProviderCapabilities,
    Provider,
    ProviderRegistry,
    ProviderUnavailableError,
    UnsupportedCapabilityError,
)


def test_local_provider_declares_capabilities_and_creates_machines():
    provider = LocalProvider()
    capabilities = provider.capabilities
    assert isinstance(provider, Provider)

    assert isinstance(capabilities, ProviderCapabilities)
    assert "process.start" in capabilities
    assert "process.wait" in capabilities
    assert "process.cancel" in capabilities
    assert isinstance(provider.create_machine(), object)


def test_provider_registry_discovers_and_negotiates_capabilities():
    registry = ProviderRegistry()
    registry.register("local", LocalProvider())

    assert registry.get("local") is not None
    selected = registry.require("local", {"process.start", "process.wait"})
    assert selected is registry.get("local")
    assert registry.find({"process.wait"}) == (("local", selected),)

    with pytest.raises(UnsupportedCapabilityError):
        registry.require("local", {"process.stream"})


def test_provider_registry_rejects_duplicate_names():
    registry = ProviderRegistry()
    registry.register("local", LocalProvider())

    with pytest.raises(ValueError, match="already registered"):
        registry.register("local", LocalProvider())


def test_retry_policy_is_mechanism_independent():
    policy = RetryPolicy(max_attempts=3)

    assert policy.should_retry(Result(status=ProcessStatus.FAILED), attempt=1)
    assert policy.should_retry(Result(status=ProcessStatus.TIMED_OUT), attempt=2)
    assert not policy.should_retry(Result(status=ProcessStatus.FAILED), attempt=3)
    assert not policy.should_retry(Result(status=ProcessStatus.CANCELLED), attempt=1)
    assert not policy.should_retry(Result(status=ProcessStatus.COMPLETED), attempt=1)


def test_failure_policy_controls_dependency_failure_behavior():
    assert FailurePolicy("skip_dependents").should_continue(
        Result(status=ProcessStatus.FAILED)
    )
    assert not FailurePolicy("fail_fast").should_continue(
        Result(status=ProcessStatus.FAILED)
    )


def test_resource_policy_validates_declared_requirements():
    policy = ResourcePolicy({"cpu": 2, "memory_mb": 1024})

    assert policy.supports({"cpu": 1, "memory_mb": 512})
    assert not policy.supports({"cpu": 4})
    assert not policy.supports({"gpu": 1})


def test_local_provider_executes_existing_process_contract():
    process = LocalProvider().create_machine().create_process(
        ProcessSpec(executable="python", arguments=("-c", "print('ok')"))
    )
    process.start()
    assert process.wait().status is ProcessStatus.COMPLETED


def test_timeout_policy_only_applies_when_no_explicit_timeout_exists():
    policy = TimeoutPolicy(5.0)
    assert policy.resolve(None) == 5.0
    assert policy.resolve(2.0) == 2.0

    with pytest.raises(ValueError, match="greater than zero"):
        TimeoutPolicy(0)


class _DiscoveryProvider:
    capabilities = ProviderCapabilities({"process.start", "process.wait"})

    def __init__(self, discovery):
        self.discovery = discovery

    def discover_capabilities(self):
        return self.discovery

    def create_machine(self, **kwargs):
        return object()


@pytest.mark.parametrize(
    ("discovery", "required", "state", "missing"),
    [
        (
            CapabilityDiscovery.supported({"process.start", "process.wait"}),
            {"process.start"},
            CapabilityState.SUPPORTED,
            set(),
        ),
        (
            CapabilityDiscovery.supported({"process.start"}),
            {"process.start", "process.wait"},
            CapabilityState.UNSUPPORTED,
            {"process.wait"},
        ),
        (
            CapabilityDiscovery.unavailable("provider offline"),
            {"process.start"},
            CapabilityState.UNAVAILABLE,
            {"process.start"},
        ),
        (
            CapabilityDiscovery.indeterminate("discovery timed out"),
            {"process.start"},
            CapabilityState.INDETERMINATE,
            {"process.start"},
        ),
    ],
)
def test_capability_negotiation_normalizes_discovery_states(
    discovery, required, state, missing
):
    registry = ProviderRegistry()
    registry.register("provider", _DiscoveryProvider(discovery))

    match = registry.negotiate("provider", required)

    assert match.state is state
    assert match.missing == frozenset(missing)
    assert match.to_dict()["state"] == state.value
    assert tuple(match.to_dict()["required"]) == tuple(sorted(required))


def test_capability_discovery_is_deterministic_and_does_not_load_provider_code_for_legacy_provider():
    registry = ProviderRegistry()
    registry.register("provider", _DiscoveryProvider(
        CapabilityDiscovery.supported({"z.capability", "a.capability"})
    ))

    first = registry.discover("provider").to_dict()
    second = registry.discover("provider").to_dict()

    assert first == second
    assert first["capabilities"] == ("a.capability", "z.capability")


def test_unavailable_capability_discovery_is_not_treated_as_supported():
    registry = ProviderRegistry()
    registry.register(
        "provider",
        _DiscoveryProvider(CapabilityDiscovery.unavailable("offline")),
    )

    with pytest.raises(ProviderUnavailableError, match="offline"):
        registry.require("provider", {"process.start"})


def test_legacy_provider_capabilities_are_normalized_as_supported():
    class LegacyProvider:
        capabilities = ProviderCapabilities({"process.start"})

        def create_machine(self, **kwargs):
            return object()

    registry = ProviderRegistry({"legacy": LegacyProvider()})

    assert registry.discover("legacy").state is CapabilityState.SUPPORTED
    assert registry.require("legacy", {"process.start"})


def test_provider_discovery_exceptions_become_indeterminate():
    class FailingProvider:
        capabilities = ProviderCapabilities({"process.start"})

        def discover_capabilities(self):
            raise RuntimeError("discovery failed")

        def create_machine(self, **kwargs):
            return object()

    registry = ProviderRegistry({"failing": FailingProvider()})

    match = registry.negotiate("failing", {"process.start"})

    assert match.state is CapabilityState.INDETERMINATE
    assert match.reason == "discovery failed"
    with pytest.raises(UnsupportedCapabilityError):
        registry.require("failing", {"process.start"})
