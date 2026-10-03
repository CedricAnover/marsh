import os

from marsh.ssh import SshConnector


def test_ssh_local_server_smoke():
    connector = SshConnector()
    connection = connector.connect(
        os.environ["MARSH_SSH_TARGET"],
        connect_kwargs={"password": os.environ["MARSH_SSH_PASSWORD"]},
    )
    stdout, stderr = connector.exec_cmd(["echo", "ssh-ok"], connection)

    assert stdout == b"ssh-ok", stderr.decode()
    assert stderr == b""
