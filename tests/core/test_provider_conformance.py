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
