import sys

import pytest

from marsh.core.domain import ProcessSpec, ProcessStatus
from marsh.core.providers import LocalProvider, ProviderConfig, ProviderRegistry, UnsupportedCapabilityError


@pytest.fixture
def local_provider():
    return LocalProvider()


def test_local_provider_conformance_success(local_provider):
    process = local_provider.create_machine().create_process(
        ProcessSpec(executable=sys.executable, arguments=("-c", "print('conform')"))
    )

    process.start()
    result = process.wait()

    assert result.status is ProcessStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout.strip() == b"conform"


def test_local_provider_conformance_duplicate_observation_is_idempotent(local_provider):
    process = local_provider.create_machine().create_process(
        ProcessSpec(executable=sys.executable, arguments=("-c", "print('once')"))
    )

    process.start()
    first = process.wait()
    second = process.wait()

    assert second == first


def test_local_provider_conformance_timeout_is_normalized(local_provider):
    process = local_provider.create_machine().create_process(
        ProcessSpec(
            executable=sys.executable,
            arguments=("-c", "import time; time.sleep(1)"),
            timeout=0.01,
        )
    )

    process.start()
    result = process.wait()

    assert result.status is ProcessStatus.TIMED_OUT


def test_local_provider_conformance_capability_mismatch_is_pre_dispatch():
    registry = ProviderRegistry({"local": LocalProvider()})
    match = registry.negotiate("local", ["process.stream"])

    assert match.satisfied is False
    assert match.missing == frozenset({"process.stream"})

    with pytest.raises(UnsupportedCapabilityError):
        registry.resolve(
            ProviderConfig("local"),
            ["process.stream"],
        )


def test_local_provider_conformance_cancellation_is_confirmed(local_provider):
    process = local_provider.create_machine().create_process(
        ProcessSpec(
            executable=sys.executable,
            arguments=("-c", "import time; time.sleep(1)"),
        )
    )

    process.start()
    process.cancel()
    result = process.wait()

    assert result.status is ProcessStatus.CANCELLED
    assert result.metadata["cancellation"] == "confirmed"


@pytest.mark.parametrize(
    "provider_factory",
    [
        pytest.param(lambda: LocalProvider(), id="local"),
        pytest.param(
            lambda: __import__("marsh.providers.docker_provider", fromlist=["DockerProvider"]).DockerProvider(
                image="python:3.12-slim"
            ),
            id="docker",
        ),
    ],
)
def test_provider_conformance_matrix_has_equivalent_capability_admission(provider_factory):
    provider = provider_factory()
    registry = ProviderRegistry({getattr(provider, "name", "provider"): provider})
    name = getattr(provider, "name", "provider")

    match = registry.negotiate(name, {"machine.create", "process.start", "process.wait"})

    assert match.satisfied
    assert match.state.value == "supported"
    assert match.to_dict()["provider"] == name


def test_provider_conformance_matrix_preserves_provider_unavailability(monkeypatch):
    from marsh.providers.docker_provider import DockerProvider

    real_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name == "docker" or name.startswith("docker."):
            raise ModuleNotFoundError("docker intentionally unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)

    provider = DockerProvider()
    registry = ProviderRegistry({"docker": provider})
    match = registry.negotiate("docker", {"machine.create"})

    assert match.state.value == "unavailable"
    assert not match.satisfied
    assert "docker" in (match.reason or "")
