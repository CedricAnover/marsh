import os
import sys

import pytest

from marsh.core.domain import ProcessSpec, ProcessStatus, Workflow, Task
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
from marsh.core.remote import ExecutionSubstrate


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


def test_unknown_provider_is_rejected_at_resolution_boundary():
    with pytest.raises(KeyError):
        ProviderRegistry({"local": LocalProvider()}).resolve(ProviderConfig("missing"))


def test_machine_and_provider_are_mutually_exclusive():
    workflow = Workflow(
        id="exclusive-selection",
        tasks=(
            Task(
                id="run",
                operation=lambda inputs, dependencies: None,
            ),
        ),
    )
    with pytest.raises(ValueError, match="cannot both be supplied"):
        execute_workflow(
            workflow,
            machine=LocalProvider().create_machine(),
            provider=ProviderConfig("local"),
            provider_registry=ProviderRegistry({"local": LocalProvider()}),
        )


def test_docker_provider_implements_the_same_capability_contract():
    from marsh.providers.docker_provider import DockerMachine, DockerProvider

    provider = DockerProvider(image="python:3.12-slim")
    assert isinstance(provider, Provider)
    assert isinstance(provider.create_machine(), DockerMachine)
    assert provider.capabilities.satisfies(
        {"machine.create", "process.start", "process.wait", "process.result"}
    )


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("CIRCLE_JOB") != "integration",
    reason="Docker provider integration runs in the CircleCI integration job",
)
def test_docker_provider_executes_real_container():
    from marsh.providers.docker_provider import DockerProvider

    process = DockerProvider(image="bash:latest").create_machine().create_process(
        ProcessSpec(executable="bash", arguments=("-lc", "printf docker-ok"))
    )
    process.start()
    result = process.wait()

    assert result.status is ProcessStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout.strip() == b"docker-ok"



def test_provider_specific_dependencies_are_optional_extras():
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
    from pathlib import Path

    project = tomllib.loads(Path(__file__).resolve().parents[2].joinpath("pyproject.toml").read_text())["project"]
    dependencies = set(project["dependencies"])
    extras = project["optional-dependencies"]

    assert not any(dependency.startswith("docker") for dependency in dependencies)
    assert not any(dependency.startswith("fabric") for dependency in dependencies)
    assert any(dependency.startswith("docker") for dependency in extras["docker"])
    assert any(dependency.startswith("fabric") for dependency in extras["ssh"])


def test_importing_core_does_not_eagerly_require_fabric():
    import subprocess

    code = """
import builtins
real_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "fabric" or name.startswith("fabric."):
        raise ModuleNotFoundError("fabric intentionally unavailable")
    return real_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
import marsh
assert marsh.Workflow
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_docker_provider_config_options_materialize_machine():
    from marsh.providers.docker_provider import DockerMachine, DockerProvider

    machine = DockerProvider(image="python:3.12-slim").create_machine(
        image="ubuntu:24.04",
        client_kwargs={"timeout": 5},
    )

    assert isinstance(machine, DockerMachine)
    assert isinstance(machine, ExecutionSubstrate)
    assert machine.machine_id == "docker:ubuntu:24.04"
    assert "process.start" in machine.capabilities
    assert machine.config.image == "ubuntu:24.04"
    assert machine.config.client_kwargs == {"timeout": 5}


def test_docker_wait_normalizes_read_timeout_to_timed_out_result():
    from requests.exceptions import ReadTimeout
    from marsh.providers.docker_provider import DockerProcess, DockerProviderConfig

    class FakeContainer:
        def wait(self, timeout):
            raise ReadTimeout("docker wait timed out")

        def remove(self, force=True):
            return None

    process = DockerProcess(
        ProcessSpec(executable="python"),
        DockerProviderConfig("python:3.12-slim"),
    )
    process._container = FakeContainer()
    process._status = ProcessStatus.RUNNING

    result = process.wait()

    assert result.status is ProcessStatus.TIMED_OUT
    assert result.error == "process timed out"
    assert process.status is ProcessStatus.TIMED_OUT


def test_docker_stop_normalizes_provider_failure():
    from marsh.providers.docker_provider import DockerProcess, DockerProviderConfig, ProviderError

    class FakeContainer:
        def stop(self, timeout=0):
            raise RuntimeError("stop failed")

        def remove(self, force=True):
            return None

    process = DockerProcess(
        ProcessSpec(executable="python"),
        DockerProviderConfig("python:3.12-slim"),
    )
    process._container = FakeContainer()
    process._status = ProcessStatus.RUNNING

    with pytest.raises(ProviderError, match="stop failed"):
        process.stop()

    assert process.status is ProcessStatus.RUNNING


def test_provider_configuration_is_not_logged_by_default(caplog):
    from marsh.providers.docker_provider import DockerProvider

    secret = "super-secret-provider-value"
    with caplog.at_level("DEBUG"):
        DockerProvider(
            image="python:3.12-slim",
            client_kwargs={"password": secret},
        )

    assert secret not in caplog.text
