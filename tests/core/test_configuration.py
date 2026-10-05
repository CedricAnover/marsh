from marsh.core.configuration import (
    MachineConfig,
    PolicyConfig,
    ProviderConfig,
    SchedulerConfig,
    WorkflowConfig,
)


def test_configuration_families_validate_at_the_boundary():
    config = WorkflowConfig.from_mapping(
        {
            "id": "configured",
            "machines": [{"name": "local-machine", "provider": "local"}],
            "providers": [{"name": "local"}],
            "scheduler": {"strategy": "thread", "max_concurrency": 4},
            "policy": {"timeout": 30},
            "tasks": [{"id": "run", "operation": "echo"}],
        }
    )
    assert isinstance(config.machines[0], MachineConfig)
    assert isinstance(config.providers[0], ProviderConfig)
    assert isinstance(config.scheduler, SchedulerConfig)
    assert isinstance(config.policy, PolicyConfig)
    assert config.scheduler.max_concurrency == 4


def test_scheduler_configuration_rejects_invalid_concurrency():
    try:
        SchedulerConfig.from_mapping({"max_concurrency": 0})
    except ValueError as exc:
        assert "positive integer" in str(exc)
    else:
        raise AssertionError("invalid concurrency was accepted")
