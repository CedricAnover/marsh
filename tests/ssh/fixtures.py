import time

import pytest
from testcontainers.core.container import DockerContainer

CONTAINER_IMAGE = "ubuntu:24.04"
CONN_KWARGS = {"password": "developer"}


@pytest.fixture(scope="function")
def ssh_container():
    """Start a regular Ubuntu container with OpenSSH for protocol-level tests."""
    container = (
        DockerContainer(CONTAINER_IMAGE, command="sleep infinity")
        .with_bind_ports(22)
    )

    container.start()

    setup = """
set -eux
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends openssh-server
useradd --create-home --shell /bin/bash developer
echo 'developer:developer' | chpasswd
mkdir -p /run/sshd
sed -ri 's/^#?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -ri 's/^#?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
/usr/sbin/sshd
"""
    result = container.exec(["bash", "-lc", setup])
    if result.exit_code != 0:
        output = result.output.decode(errors="replace")
        container.stop(force=True)
        raise RuntimeError(f"Failed to configure OpenSSH test container: {output}")

    time.sleep(0.5)
    yield container
    container.stop(force=True)
