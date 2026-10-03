from marsh.ssh.ssh_connector import SshConnector


class _Result:
    stdout = "ok"
    stderr = ""


class _Connection:
    def __init__(self):
        self.run_kwargs = None
        self.closed = False

    def run(self, command, **kwargs):
        self.run_kwargs = (command, kwargs)
        return _Result()

    def close(self):
        self.closed = True


def test_ssh_connector_preserves_identity_file_and_connection_kwargs(monkeypatch):
    captured = {}

    def fake_connection(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _Connection()

    monkeypatch.setattr("marsh.ssh.ssh_connector.Connection", fake_connection)

    connector = SshConnector()
    connection = connector.connect(
        "developer@example",
        connect_kwargs={"key_filename": "/tmp/id_ed25519"},
    )

    assert connection is not None
    assert captured["kwargs"]["connect_kwargs"]["key_filename"] == "/tmp/id_ed25519"


def test_ssh_connector_preserves_prompt_and_input_run_options(monkeypatch):
    connection = _Connection()
    connector = SshConnector()

    stdout, stderr = connector.exec_cmd(
        ["read", "-p", "Name: ", "name"],
        connection,
        in_stream="input-stream",
        pty=True,
    )

    command, kwargs = connection.run_kwargs
    assert command == "read -p Name:  name"
    assert kwargs["in_stream"] == "input-stream"
    assert kwargs["pty"] is True
    assert stdout == b"ok"
    assert stderr == b""
    assert connection.closed
