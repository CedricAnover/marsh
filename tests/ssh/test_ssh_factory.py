import pytest

from marsh.ssh import SshFactory, SshCommandGrammar, SshConnector
from .fixtures import sysbox_container, CONN_KWARGS


@pytest.fixture
def setup_ssh_factory():
    ssh_factory = SshFactory(
        fabric_config=None,
        connection_args=("developer@127.0.0.1:2222",),
        connection_kwargs=dict(connect_kwargs=CONN_KWARGS),
    )
    return ssh_factory


def test_ssh_factory_initialization(setup_ssh_factory):
    ssh_factory = setup_ssh_factory
    assert isinstance(ssh_factory, SshFactory)
    assert ssh_factory._config is None
    assert isinstance(ssh_factory._conn_args, tuple)
    assert ssh_factory._conn_args[0] == "developer@127.0.0.1:2222"
    assert isinstance(ssh_factory._conn_kwargs, dict)
    assert ssh_factory._conn_kwargs["connect_kwargs"] == {"password": "developer"}


def test_ssh_factory_create_command_grammar(setup_ssh_factory):
    ssh_factory = setup_ssh_factory
    cmd_grammar = ssh_factory.create_command_grammar()
    assert isinstance(cmd_grammar, SshCommandGrammar)


def test_ssh_factory_create_connector(setup_ssh_factory):
    ssh_factory = setup_ssh_factory
    connector = ssh_factory.create_connector()
    assert isinstance(connector, SshConnector)


def test_ssh_factory_create_cmd_runner(sysbox_container, setup_ssh_factory):
    ssh_factory = setup_ssh_factory
    cmd_runner = ssh_factory.create_cmd_runner(["echo Hello World"])
    stdout, stderr = cmd_runner(b"", b"")
    assert callable(cmd_runner)
    assert stdout.decode().strip() == "Hello World"
    assert stderr.decode().strip() == ""


def test_ssh_factory_create_cmd_runner_with_invalid_command(sysbox_container, setup_ssh_factory):
    ssh_factory = setup_ssh_factory
    cmd_runner = ssh_factory.create_cmd_runner(["cho Hello World"])  # <-- Invalid `cho`
    stdout, stderr = cmd_runner(b"", b"")
    assert callable(cmd_runner)
    assert stdout.decode().strip() == ""

    # TODO: Improve error handling and enumerate all possible scenarios
    assert stderr.decode().strip() != ""


def test_ssh_factory_create_chained_cmd_runner(sysbox_container, setup_ssh_factory):
    ssh_factory = setup_ssh_factory
    cmd_runner = ssh_factory.create_chained_cmd_runner(["echo Hello", "echo World"])
    stdout, stderr = cmd_runner(b"", b"")
    assert callable(cmd_runner)
    assert stdout.decode().strip() == "Hello\nWorld"
