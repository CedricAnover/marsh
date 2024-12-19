import time
import pytest
from testcontainers.core.container import DockerContainer

# Important: Use `-s` in `poetry run pytest -s tests/ssh/test_***.py` to show output.

SYSBOX_IMAGE = "cedricanover94/sysbox-jammy:latest"
RUNTIME = "sysbox-runc"
CONN_KWARGS = {"password": "developer"}  # https://github.com/CedricAnover/Sysbox-Development-Workstation


@pytest.fixture(scope="function")
def sysbox_container():
    """Fixture to start and stop the Sysbox container."""
    docker_options = {
        "runtime": RUNTIME,
        "tty": True,
        "hostname": "sysbox-jammy-host",
        "remove": True,
    }

    # Instantiate and configure the container
    container = (
        DockerContainer(SYSBOX_IMAGE)
        .with_kwargs(**docker_options)
        .with_bind_ports(22, 2222)
    )

    # Set environment variable and start container
    container.start()

    # Allow some time for the container to initialize
    time.sleep(2.5)

    # Provide the container to the test function
    yield container

    # Stop the container after the test
    container.stop(force=True)
