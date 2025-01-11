import pytest

from marsh import Conveyor
from marsh.dag import Node


def mock_cmd_runner(stdout: bytes, stderr: bytes) -> tuple[bytes, bytes]:
    return stdout + b"_cmd_executed", stderr


def test_node_initialization():
    conveyor = Conveyor()
    node = Node(name="test_node", conveyor=conveyor)

    assert node.name == "test_node"
    assert node.conveyor is conveyor


def test_node_start_single_command():
    conveyor = Conveyor().add_cmd_runner(mock_cmd_runner)
    node = Node(name="test_node", conveyor=conveyor)
    stdout, stderr = node.start()

    assert stdout == b"_cmd_executed"
    assert stderr == b""


def test_node_start_multiple_commands():
    def cmd_runner_2(stdout: bytes, stderr: bytes) -> tuple[bytes, bytes]:
        return stdout + b"_second_cmd", stderr

    conveyor = Conveyor().add_cmd_runner(mock_cmd_runner).add_cmd_runner(cmd_runner_2)
    node = Node(name="test_node", conveyor=conveyor)
    stdout, stderr = node.start()

    assert stdout == b"_cmd_executed_second_cmd"
    assert stderr == b""


def test_node_with_kwargs():
    def cmd_with_kwargs(stdout: bytes, stderr: bytes, suffix: bytes) -> tuple[bytes, bytes]:
        return stdout + suffix, stderr

    conveyor = Conveyor().add_cmd_runner(cmd_with_kwargs, suffix=b"_kwarg_test")
    node = Node(name="test_node", conveyor=conveyor)
    stdout, stderr = node.start()

    assert stdout == b"_kwarg_test"
    assert stderr == b""


def test_node_empty_conveyor():
    conveyor = Conveyor()
    node = Node(name="test_node", conveyor=conveyor)
    stdout, stderr = node.start()

    assert stdout == b""
    assert stderr == b""


def test_node_invalid_cmd_runner():
    with pytest.raises(TypeError):
        Conveyor().add_cmd_runner("not_a_callable")
