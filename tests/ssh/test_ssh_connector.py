import time

import fabric
import pytest

from marsh.ssh import SshConnector
from .fixtures import CONN_KWARGS, _connection_target, ssh_container


@pytest.fixture
def setup_ssh_connector_no_config():
    return SshConnector()



def test_ssh_connector_initialization_without_fabric_config(setup_ssh_connector_no_config):
    ssh_connector = setup_ssh_connector_no_config
    assert isinstance(ssh_connector, SshConnector)
    assert ssh_connector._config is None


def test_ssh_connector_connect(setup_ssh_connector_no_config, ssh_container):
    ssh_connector = setup_ssh_connector_no_config
    connection = ssh_connector.connect(
        _connection_target(ssh_container),
        connect_kwargs=CONN_KWARGS,
    )
    assert connection is not None
    assert isinstance(connection, fabric.Connection)


def test_ssh_connector_disconnect(setup_ssh_connector_no_config, ssh_container):
    ssh_connector = setup_ssh_connector_no_config
    connection = ssh_connector.connect(
        _connection_target(ssh_container),
        connect_kwargs=CONN_KWARGS,
    )
    time.sleep(0.7)
    ssh_connector.disconnect(connection)
    assert not connection.is_connected


def test_ssh_connector_exec_cmd(setup_ssh_connector_no_config, ssh_container):
    ssh_connector = setup_ssh_connector_no_config
    connection = ssh_connector.connect(
        _connection_target(ssh_container),
        connect_kwargs=CONN_KWARGS,
    )
    time.sleep(0.7)
    stdout, stderr = ssh_connector.exec_cmd(
        ["echo", "Hello", "World"],
        connection,
    )
    assert stderr == b""
    assert stdout.decode().strip() == "Hello World"
