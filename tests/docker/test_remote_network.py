import time

import pytest


@pytest.mark.integration
def test_two_docker_containers_communicate_over_user_defined_network():
    docker = pytest.importorskip("docker")
    try:
        client = docker.from_env()
    except docker.errors.DockerException as exc:
        pytest.skip(f"Docker daemon unavailable: {exc}")
    network = client.networks.create("marsh-v041-conformance", driver="bridge")
    server = None
    peer = None
    try:
        server_code = (
            "import socket; "
            "s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); "
            "s.bind(('0.0.0.0',23456)); s.listen(1); "
            "c,_=s.accept(); data=c.recv(1024); c.sendall(data+b'-remote'); c.close(); s.close()"
        )
        server = client.containers.run(
            "python:3.12-slim",
            ["python", "-c", server_code],
            name="marsh-v041-server",
            network=network.name,
            detach=True,
        )
        # The client retries until the server is listening, avoiding timing sleeps
        # as the readiness mechanism.
        peer_code = (
            "import socket,time; "
            "data=b'conformance'; "
            "last=None; "
            "for _ in range(30):\n"
            "  try:\n"
            "    s=socket.create_connection(('marsh-v041-server',23456),timeout=1); s.sendall(data); "
            "    print(s.recv(1024).decode()); s.close(); break\n"
            "  except OSError as e:\n"
            "    last=e; time.sleep(0.1)\n"
            "else: raise last"
        )
        peer = client.containers.run(
            "python:3.12-slim",
            ["python", "-c", peer_code],
            network=network.name,
            detach=False,
            remove=True,
        )
        assert peer.decode().strip() == "conformance-remote"
    finally:
        if server is not None:
            try:
                server.remove(force=True)
            except docker.errors.NotFound:
                pass
        network.remove()
        client.close()
