import time

import fabric
import pytest
from testcontainers.core.container import DockerContainer

from marsh.ssh import SshConnector

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
    # os.environ["DOCKER_RUNTIME"] = RUNTIME
    container.start()

    # Allow some time for the container to initialize
    time.sleep(2.5)

    # Provide the container to the test function
    yield container

    # Stop the container after the test
    container.stop(force=True)


@pytest.fixture
def setup_ssh_connector_no_config():
    # With no fabric.Config
    return SshConnector()


def test_ssh_connector_initialization_without_fabric_config(setup_ssh_connector_no_config):
    ssh_connector = setup_ssh_connector_no_config
    assert isinstance(ssh_connector, SshConnector)
    assert ssh_connector._config is None


def test_ssh_connector_connect(setup_ssh_connector_no_config, sysbox_container):
    ssh_connector = setup_ssh_connector_no_config
    connection = ssh_connector.connect(
        "developer@127.0.0.1:2222",
        connect_kwargs=CONN_KWARGS
    )
    assert connection is not None
    assert isinstance(connection, fabric.Connection)


def test_ssh_connector_disconnect(setup_ssh_connector_no_config, sysbox_container):
    ssh_connector = setup_ssh_connector_no_config
    connection = ssh_connector.connect(
        "developer@127.0.0.1:2222",
        connect_kwargs=CONN_KWARGS
    )
    time.sleep(0.7)
    ssh_connector.disconnect(connection)
    assert not connection.is_connected


def test_ssh_connector_exec_cmd(setup_ssh_connector_no_config, sysbox_container):
    container = sysbox_container
    ssh_connector = setup_ssh_connector_no_config
    connection = ssh_connector.connect(
        "developer@127.0.0.1:2222",
        connect_kwargs=CONN_KWARGS
    )
    time.sleep(0.7)
    stdout, stderr = ssh_connector.exec_cmd(
        ["echo", "Hello", "World"],
        connection,
    )
    assert stdout.decode().strip() == "Hello World"
    assert stderr.decode().strip() == ""
