import sys

import pytest

from marsh.core.domain import ProcessSpec, ProcessStatus, Result, Workflow, Task
from marsh.core.providers import (
    LocalProvider,
    Provider,
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigurationError,
    ProviderRegistry,
    UnsupportedCapabilityError,
)
from marsh.core.runtime import execute_workflow


def test_provider_config_normalizes_name_and_options():
    config = ProviderConfig(" local ", {"region": "test"})
    assert config.name == "local"
    assert config.options == {"region": "test"}


def test_provider_registry_rejects_invalid_provider_and_resolves_deterministically():
    registry = ProviderRegistry({"local": LocalProvider()})
    selected = registry.resolve(ProviderConfig("local"), {"process.start", "process.wait"})
    assert isinstance(selected, Provider)
    assert registry.find({"process.wait"}) == (("local", selected),)

    with pytest.raises(ProviderConfigurationError):
        registry.register("local", LocalProvider())

    with pytest.raises(UnsupportedCapabilityError):
        registry.resolve(ProviderConfig("local"), {"process.stream"})


def test_execute_workflow_can_select_provider_without_changing_workflow_semantics():
    workflow = Workflow(
        id="provider-selection",
        tasks=(
            Task(
                id="run",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=("-c", "print('provider-ok')"),
                ),
            ),
        ),
    )

    results = execute_workflow(
        workflow,
        provider=ProviderConfig("local"),
        provider_registry=ProviderRegistry({"local": LocalProvider()}),
    )

    assert results["run"].status is ProcessStatus.COMPLETED
    assert results["run"].stdout.strip() == b"provider-ok"


def test_provider_is_a_mechanism_boundary():
    provider = LocalProvider()
    assert isinstance(provider, Provider)
    assert isinstance(provider.capabilities, ProviderCapabilities)
    assert provider.capabilities.satisfies(
        {"machine.create", "process.start", "process.wait"}
    )


def test_local_provider_options_are_rejected():
    with pytest.raises(ProviderConfigurationError, match="unsupported local provider options"):
        LocalProvider().create_machine(region="test")
