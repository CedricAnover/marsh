import subprocess
import time

import pytest

from marsh.docker import DockerContainer, DockerCommandExecutor


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


@pytest.fixture(scope="function")
def command_executor(request):
    args, kwargs = request.param
    docker_command_executor = DockerCommandExecutor(*args, **kwargs)
    return docker_command_executor
