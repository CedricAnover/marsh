import pytest

from marsh.core.domain import ProcessSpec, ProcessStatus, Result, Workflow, Task
from marsh.core.policies import FailurePolicy, ResourcePolicy, RetryPolicy, TimeoutPolicy
from marsh.core.providers import (
    LocalProvider,
    ProviderCapabilities,
    Provider,
    ProviderRegistry,
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
