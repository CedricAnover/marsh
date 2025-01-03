import subprocess
import time
from threading import Timer

import pytest

from marsh.exceptions import DockerError, DockerClientError
from marsh.docker import DockerContainer
from .fixtures import _get_container_from_filter, docker_container


def test_docker_container_instantiation():
    # Without using context manager
    container = DockerContainer("bash:latest", name="test-container")
    container._clean()
    assert isinstance(container, DockerContainer)
    assert container._image == "bash:latest"
    assert container._name == "test-container"
    assert container._timeout == 600


def test_docker_container_default_name():
    container = DockerContainer("bash:latest")
    container._clean()
    assert container._name.startswith("ephemeral-container")


def test_docker_container_resource_lifecycle():
    # Assert that the Docker Container does not exist after getting out of context.
    container_name = "test-container"

    with DockerContainer("bash:latest", name=container_name) as container:
        # Assert container resource is created
        assert container.status == "created"

    stdout, stderr = _get_container_from_filter(container_name)

    # Assert container resource is removed
    assert stdout == ""
    assert stderr == ""


def test_docker_container_resource_cleanup_on_error(mocker):
    # Patch the threading.Timer constructor and introduce side effect by raising error
    mock_timer = mocker.patch('threading.Timer', autospec=True)
    mock_timer_start = mock_timer.return_value.start
    mock_timer_start.side_effect = ValueError("Mocked Error")

    container_name = "test-container"
    with pytest.raises(DockerError, match="Mocked Error"):
        with DockerContainer("bash:latest", name=container_name) as container:
            pass

    # Assert that the container is removed in an event of an error
    stdout, stderr = _get_container_from_filter(container_name)
    assert stdout == ""
    assert stderr == ""


def test_docker_container_timeout_handling():
    timeout = 2
    container_name = "test-container"
    with DockerContainer("bash:latest", name=container_name, timeout=timeout) as container:
        with pytest.raises(TimeoutError, match=f"Timeout reached for container '{container_name}'."):
            # Sleep longer than the timeout to trigger the timeout handling
            # time.sleep(timeout + 1.5)
            container.exec_run(["bash", "-c", f"sleep {timeout + 1.5}"])

    stdout, stderr = _get_container_from_filter(container_name)
    assert stdout == ""
    assert stderr == ""


def test_docker_container_client_connection_issues(mocker):
    # Mock and simulate connection issue.
    mock_client = mocker.patch('docker.DockerClient', autospec=True)
    mock_client.side_effect = ValueError("Mocked Error")

    container_name = "test-container"
    with pytest.raises(DockerClientError, match="Mocked Error"):
        with DockerContainer("bash:latest", name=container_name) as container:
            pass

    # Assert that the container is removed in an event of an error
    stdout, stderr = _get_container_from_filter(container_name)
    assert stdout == ""
    assert stderr == ""


@pytest.mark.parametrize('docker_container', ['test-container'], indirect=True)
def test_docker_container_exec_run(docker_container):
    # Run basic command, and assert the correct/expected STDOUT & STDERR.
    container = docker_container
    result = container.exec_run(
        ["bash", "-c", "echo Hello World"]
    )
    # Assert that exit code is 0 (success) and the value expected stdout
    assert result.exit_code == 0
    assert result.output.decode().strip() == "Hello World"


@pytest.mark.parametrize('docker_container', ['test-container'], indirect=True)
def test_docker_container_exec_run_with_invalid_command_in_container(docker_container):
    container = docker_container
    command = "mock_invalid_command"
    result = container.exec_run(["bash", "-c", f'{command}'])
    assert result.exit_code != 0
    assert result.output.decode().strip() == \
           f"bash: line 1: {command}: command not found"


def test_docker_container_create_another_container_with_same_name():
    container_name = "test_container_same_name"
    with DockerContainer("bash:latest", name=container_name) as container:
        with pytest.raises(DockerError):
            with DockerContainer("bash:latest", name=container_name) as container_2:
                pass
