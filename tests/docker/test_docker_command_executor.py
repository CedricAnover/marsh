import pytest

from marsh.docker import DockerCommandExecutor


def test_instantiation():
    pass


def test_basic_command_without_piping():
    pass


def test_basic_command_with_piping():
    pass


def test_chained_multiple_docker_executors():
    # Test how multiple command runners built from `DockerCommandExecutor`
    # would behave along with conveyor.
    pass


def test_docker_cleanup():
    pass


def test_with_none_zero_exit_code():
    # Mock and simulate when exist code is non-zero (an error).
    pass


def test_timeout_handling():
    pass


def test_non_existent_docker_image():
    pass


def test_container_name_exists():
    pass


def test_instantiation_with_invalid_client_parameters():
    pass


def test_instantiation_with_invalid_container_constructor_parameters():
    pass


def test_with_invalid_run_keyword_arguments():
    pass


def test_concurrent_command_execution():
    pass


def test_injecting_environment_variable():
    pass


def test_change_working_directory():
    pass
