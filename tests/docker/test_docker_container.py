import pytest

from marsh.docker import DockerContainer


def test_docker_container_instantiation():
    # Without using context manager
    pass


def test_docker_container_resource_created_on_entry():
    # Assert that a Container is created.
    # Note: Does not necessarily have to check if the container
    #   is removed. 
    pass


def test_docker_container_resource_cleanup_on_exit():
    # Assert that the Docker Container does not
    # exist after getting out of context.
    pass


def test_docker_container_resource_cleanup_on_error():
    # Test that the container is removed in an event of an error.
    pass


def test_docker_container_timeout_handling():
    # Assert Raises Timeout Error
    pass


def test_docker_container_client_connection_issues():
    # Mock and simulate connection issue.
    pass


def test_docker_container_exec_run():
    # Run basic command, and assert the correct/expected STDOUT & STDERR.
    pass
