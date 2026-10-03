import os

import pytest

from marsh.ssh import SshConnector


@pytest.mark.skipif(
    not os.environ.get("MARSH_SSH_TARGET")
    or not os.environ.get("MARSH_SSH_PASSWORD"),
    reason="local SSH smoke target/password not configured",
)
def test_ssh_local_server_smoke():
    connector = SshConnector()
    connection = connector.connect(
        os.environ["MARSH_SSH_TARGET"],
        connect_kwargs={"password": os.environ["MARSH_SSH_PASSWORD"]},
    )
    stdout, stderr = connector.exec_cmd(["echo", "ssh-ok"], connection)

    assert stdout == b"ssh-ok\n", stderr.decode()
    assert stderr == b""
