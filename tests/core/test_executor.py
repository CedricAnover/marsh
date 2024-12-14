import subprocess
from typing import Tuple, Any

import pytest
from pytest_mock import mocker

from marsh import (
    Executor,
    LocalCommandExecutor,
    RemoteCommandExecutor
)


#==========================================================================================================
#=========================== Setups
@pytest.fixture
def local_executor(mocker):
    """Fixture for LocalCommandExecutor."""
    # Mock CommandGrammar with mocker
    mock_command_grammar = mocker.patch("marsh.core.command_grammar.CommandGrammar", autospec=True)
    command_grammar = mock_command_grammar.return_value
    command_grammar.program_path.return_value = "/path/to/program"
    command_grammar.options.return_value = ["--option1", "value1", "--option2", "value2"]
    command_grammar.program_args.return_value = ["arg1", "arg2"]
    command_grammar.build_cmd.return_value = [
        command_grammar.program_path.return_value,
        *command_grammar.options.return_value,
        *command_grammar.program_args.return_value
    ]

    # Create an instance of LocalCommandExecutor with the mocked command_grammar
    return LocalCommandExecutor(command_grammar=command_grammar)


#==========================================================================================================
#============== Executor
def test_executor_abc_instantiation():
    # Test that the abstract Executor class cannot be instantiated
    with pytest.raises(TypeError):
        Executor()

#==========================================================================================================
#============== LocalCommandExecutor

def test_local_command_executor_run(mocker, local_executor):
    # Mock the subprocess.Popen instance from local_executor.create_popen_with_pipe() method and patch 
    # the subprocess.Popen.communicate method to return a fake result.
    mock_popen = mocker.patch("subprocess.Popen", autospec=True)
    mock_popen.return_value.communicate.return_value = b"test-stdout", b"test-stderr"  # Intercept and replace with fake values

    stdout, stderr = local_executor.run(b"", b"")
    assert stdout == b"test-stdout"
    assert stderr == b"test-stderr"

    mock_popen.assert_called_once_with(
        ['/path/to/program', '--option1', 'value1', '--option2', 'value2', 'arg1', 'arg2'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_invalid_command(mocker, local_executor):
    mocker.patch.object(local_executor.command_grammar, 'build_cmd', return_value=["nonexistent_command"])

    with pytest.raises(FileNotFoundError):
        local_executor.run(b"", b"")


def test_empty_command(local_executor, mocker):
    mocker.patch.object(local_executor.command_grammar, 'build_cmd', return_value=[])

    with pytest.raises((OSError, IndexError)):
        local_executor.run(b"", b"")


def test_timeout(local_executor, mocker, monkeypatch):
    mocker.patch.object(local_executor.command_grammar, 'build_cmd', return_value=["bash", "-c", "sleep 5"])
    local_executor.timeout = 1  # Set the timeout class field to 1

    with pytest.raises(subprocess.TimeoutExpired):
        local_executor.run(b"", b"")  # Setting a short timeout


def test_pipe_prev_stdout(local_executor, mocker):
    mocker.patch.object(local_executor.command_grammar, 'build_cmd', return_value=["cat"])

    # Mock communicate to simulate the output from a previous process
    mock_popen = mocker.patch("subprocess.Popen", autospec=True)
    mock_popen.return_value.communicate.return_value = b"test-stdout", b"test-stderr"

    stdout, stderr = local_executor.run(b"input-for-cat", b"")
    assert stdout == b"test-stdout"
    assert stderr == b"test-stderr"


def test_callback_function(local_executor, mocker):
    mocker.patch.object(local_executor.command_grammar, 'build_cmd', return_value=["echo", "test"])

    def custom_callback(process, stdout, stderr, *args, **kwargs):
        # Modify the output from the subprocess
        return b"modified-stdout", b"modified-stderr"

    stdout, stderr = local_executor.run(b"", b"", callback=custom_callback)
    assert stdout == b"modified-stdout"
    assert stderr == b"modified-stderr"


def test_large_command(local_executor, mocker):
    long_args = ["--option{}".format(i) for i in range(1000)]  # Large number of options
    mocker.patch.object(local_executor.command_grammar, 'build_cmd', return_value=["echo", *long_args])

    mock_popen = mocker.patch("subprocess.Popen", autospec=True)
    mock_popen.return_value.communicate.return_value = b"test-stdout", b"test-stderr"

    stdout, stderr = local_executor.run(b"", b"")
    assert stdout == b"test-stdout"
    assert stderr == b"test-stderr"


def test_empty_output(local_executor, mocker):
    mocker.patch.object(local_executor.command_grammar, 'build_cmd', return_value=["echo", "test"])

    mock_popen = mocker.patch("subprocess.Popen", autospec=True)
    mock_popen.return_value.communicate.return_value = b"", b""  # Simulate empty output

    stdout, stderr = local_executor.run(b"", b"")
    assert stdout == b""
    assert stderr == b""


def test_invalid_callback_return(local_executor, mocker):
    mocker.patch.object(local_executor.command_grammar, 'build_cmd', return_value=["bash", "-c", "echo TEST"])

    def invalid_callback(process, stdout, stderr, *args, **kwargs):
        pass  # Incorrect return type

    with pytest.raises(ValueError):
        local_executor.run(b"", b"", callback=invalid_callback)

#==========================================================================================================
#============== RemoteCommandExecutor
class MockExternalConnection:
    def __init__(self):
        self.is_connected = True

    def run(self, command: str):
        return command.encode(), b"mock_stderr"

    def close(self):
        self.is_connected = False


@pytest.fixture
def setup_remote_executor(mocker):
    # Mock the RemoteCommandExecutor
    mock_remote_executor = mocker.patch("marsh.core.executor.RemoteCommandExecutor", autospec=True)
    remote_executor = mock_remote_executor.return_value

    remote_executor.establish_connection.return_value = MockExternalConnection()

    # Use side_effect for close_connection to ensure proper behavior
    def mock_close_connection(connection, *args, **kwargs):
        connection.close(*args, **kwargs)

    remote_executor.close_connection.side_effect = mock_close_connection
    remote_executor.execute_command.return_value = (b"mock_stdout", b"mock_stderr")

    # Remind: Make sure to pass the remote_executor instance for `self`
    remote_executor.run.side_effect = RemoteCommandExecutor.run

    return remote_executor


def test_remote_command_executor_establish_connection(setup_remote_executor):
    remote_executor = setup_remote_executor
    connection = remote_executor.establish_connection()
    assert isinstance(connection, MockExternalConnection)
    assert connection.is_connected is True


def test_remote_command_executor_close_connection(setup_remote_executor):
    remote_executor = setup_remote_executor
    connection = remote_executor.establish_connection()
    remote_executor.close_connection(connection)
    assert connection.is_connected is False


def test_remote_command_executor_execute_command(setup_remote_executor):
    remote_executor = setup_remote_executor
    connection = remote_executor.establish_connection()
    stdout, stderr = remote_executor.execute_command(connection, b"", b"")
    assert stdout == b"mock_stdout"
    assert stderr == b"mock_stderr"


def test_remote_command_executor_run(setup_remote_executor):
    remote_executor = setup_remote_executor
    connection = remote_executor.establish_connection()

    assert connection.is_connected is True
    stdout, stderr = remote_executor.run(remote_executor, b"", b"")
    assert stdout == b"mock_stdout"
    assert stderr == b"mock_stderr"
    assert connection.is_connected is False
