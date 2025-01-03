import subprocess
import time
from threading import Timer

import pytest

from marsh.exceptions import DockerError, DockerClientError
from marsh.docker import DockerContainer


def _get_container_from_filter(container_name: str) -> tuple[str, str]:
    # Get list of containers with the container name
    result = \
        subprocess.run(
            [
                "bash", "-c",
                f'docker ps -a --filter "name={container_name}" --format "{{.Names}}"'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    return result.stdout.decode().strip(), result.stderr.decode().strip()


@pytest.fixture(scope="function")
def docker_container(request):
    """
    Fixture for creating named docker container.

    Example:
        ```python
        @pytest.mark.parametrize('docker_container', ['test-container'], indirect=True)
        def test_some_function(docker_container):
            container = docker_container
            container.name
            ...
        ```
    """
    container_name = request.param  # This allows you to pass a parameter
    with DockerContainer("bash:latest", name=container_name) as container:
        # Assert that the container is created successfully
        assert container.status == "created"
        yield container

    # # Assert container resource is removed
    stdout, stderr = _get_container_from_filter(container.name)
    assert stdout == ""
    assert stderr == ""
    time.sleep(0.7)


def test_docker_container_instantiation():
    # Without using context manager
    container = DockerContainer("bash:latest", name="test-container")
    assert isinstance(container, DockerContainer)
    assert container._image == "bash:latest"
    assert container._name == "test-container"
    assert container._timeout == 600


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
            time.sleep(timeout + 1.5)

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
