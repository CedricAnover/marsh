from marsh.docker.docker_executor import DockerContainer


class _FakeContainer:
    def __init__(self):
        self.name = "test-container"
        self.stopped = False

    def start(self):
        return None

    def stop(self, timeout=0):
        self.stopped = True


class _FakeContainers:
    def __init__(self):
        self.container = _FakeContainer()

    def create(self, *args, **kwargs):
        self.container.name = kwargs["name"]
        return self.container

    def list(self, all=True):
        return [self.container]


class _FakeClient:
    def __init__(self):
        self.containers = _FakeContainers()
        self.closed = False

    def close(self):
        self.closed = True


def test_docker_timeout_is_propagated_to_context_caller(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(
        "marsh.docker.docker_executor.docker.DockerClient",
        lambda *args, **kwargs: client,
    )

    container = DockerContainer(
        "image",
        name="test-container",
        timeout=60,
        start_timeout=0,
    )

    with pytest.raises(TimeoutError, match="Timeout reached for container 'test-container'."):
        with container as fake:
            assert fake is client.containers.container
            container._throw_timeout_error()

    assert client.closed
    assert fake.stopped
