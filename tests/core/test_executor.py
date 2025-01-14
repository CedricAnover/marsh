import subprocess
from typing import Tuple, Any

import pytest
from pytest_mock import mocker

from marsh import (
    Executor,
    LocalCommandExecutor,
    RemoteCommandExecutor,
    PythonExecutor
)


# ==========================================================================================================
# =========================== Setups
@pytest.fixture
def local_executor(mocker):
    """Fixture for LocalCommandExecutor."""
    # Mock CommandGrammar with mocker
    mock_command_grammar = mocker.patch("marsh.core.command_grammar.CommandGrammar", autospec=True)
    command_grammar = mock_command_grammar.return_value
    command_grammar.build_cmd.side_effect = \
        lambda *args, **kwargs: ['/path/to/program', '--option1', 'value1', '--option2', 'value2', 'arg1', 'arg2']

    # Create an instance of LocalCommandExecutor with the mocked command_grammar
    return LocalCommandExecutor(command_grammar=command_grammar)


# ==========================================================================================================
# ============== Executor
def test_executor_abc_instantiation():
    # Test that the abstract Executor class cannot be instantiated
    with pytest.raises(TypeError):
        Executor()


# ==========================================================================================================
# ============== LocalCommandExecutor

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


# ==========================================================================================================
# ============== RemoteCommandExecutor
class MockExternalConnection:
    def __init__(self):
        self.is_connected = True

    def run(self, command: str):
        return command.encode(), b"mock_stderr"

    def close(self):
        self.is_connected = False


@pytest.fixture
def setup_connector(mocker):
    mock_connector = mocker.patch("marsh.core.connector.Connector", autospec=True)
    connector = mock_connector.return_value
    connector.connect.return_value = MockExternalConnection()

    def mock_disconnect(connection):
        connection.close()

    connector.disconnect.side_effect = mock_disconnect

    def mock_exec_cmd(command: list[str], connection):
        return b"mock_stdout", b"mock_stderr"

    connector.exec_cmd.side_effect = mock_exec_cmd
    return connector


@pytest.fixture
def setup_command_grammar(mocker):
    mock_command_grammar = mocker.patch("marsh.core.command_grammar.CommandGrammar", autospec=True)
    command_grammar = mock_command_grammar.return_value
    command_grammar.build_cmd.return_value = ["/path/to/program", "--option=value", "arg"]
    return command_grammar


def test_remote_command_executor_initialization(setup_connector, setup_command_grammar):
    connector = setup_connector
    command_grammar = setup_command_grammar
    remote_command_executor = RemoteCommandExecutor(connector, command_grammar)

    assert remote_command_executor.connector == connector
    assert remote_command_executor.command_grammar == command_grammar
    assert isinstance(remote_command_executor, RemoteCommandExecutor)


def test_remote_command_executor_run(setup_connector, setup_command_grammar):
    connector = setup_connector
    command_grammar = setup_command_grammar
    remote_command_executor = RemoteCommandExecutor(connector, command_grammar)

    stdout, stderr = remote_command_executor.run(b"", b"")
    assert stdout == b"mock_stdout"
    assert stderr == b"mock_stderr"


# ==========================================================================================================
# ============== PythonExecutor

def test_python_executor_initialization_exec():
    import textwrap

    py_code = """
    x = 1
    y = 2
    """

    python_executor = PythonExecutor(py_code, mode="exec")

    assert isinstance(python_executor, PythonExecutor)
    assert python_executor._mode == "exec"
    assert python_executor._namespace == {}
    assert python_executor._use_pickle is False
    assert python_executor._py_code == textwrap.dedent(py_code)


def test_python_executor_initialization_eval():
    py_code = """1 + 1"""
    python_executor = PythonExecutor(py_code, mode="eval")

    assert isinstance(python_executor, PythonExecutor)
    assert python_executor._mode == "eval"
    assert python_executor._namespace == {}
    assert python_executor._use_pickle is False
    assert python_executor._py_code == py_code


def test_python_executor_initialization_invalid_mode():
    with pytest.raises(ValueError, match="`mode` must be 'eval' or 'exec'."):
        py_code = "1 + 1"
        PythonExecutor(py_code, mode="mock_invalid_mode")


def test_python_executor_initialization_empty_code():
    py_code = ""

    with pytest.raises(ValueError, match="Python code is empty."):
        PythonExecutor(py_code, mode="exec")

    with pytest.raises(ValueError, match="Python code is empty."):
        PythonExecutor(py_code, mode="eval")


def test_python_executor_run_eval():
    py_code = "1 + 1"
    python_executor = PythonExecutor(py_code, mode="eval")

    stdout, stderr = python_executor.run(b"", b"")
    assert stdout.decode().strip() == "2"
    assert stderr.decode().strip() == ""


def test_python_executor_run_eval_pipe_prev_output_streams():
    py_code = "int(x_stdout.decode()) + int(x_stderr.decode())"
    python_executor = PythonExecutor(py_code, mode="eval")

    stdout, stderr = python_executor.run(b"1", b"1")
    assert stdout.decode().strip() == "2"
    assert stderr.decode().strip() == ""


def test_python_executor_run_exec():
    py_code = """
    x = 1
    y = 2

    exec_result = x + y
    """
    python_executor = PythonExecutor(py_code, mode="exec")
    stdout, stderr = python_executor.run(b"", b"")

    assert stdout.decode().strip() == "3"
    assert stderr.decode().strip() == ""


def test_python_executor_run_exec_not_storing_result_to_exec_result():
    py_code = """
    x = 1
    y = 2
    """
    python_executor = PythonExecutor(py_code, mode="exec")
    stdout, stderr = python_executor.run(b"", b"")

    assert stdout.decode().strip() == "None"
    assert stderr.decode().strip() == ""


def test_python_executor_run_exec_pipe_prev_output_streams():
    py_code = """
    x = int(x_stdout.decode())
    y = int(x_stderr.decode())

    exec_result = x + y
    """
    python_executor = PythonExecutor(py_code, mode="exec")
    stdout, stderr = python_executor.run(b"1", b"2")

    assert stdout.decode().strip() == "3"
    assert stderr.decode().strip() == ""


def test_python_executor_eval_pickle_handling():
    import pickle

    py_code = "1 + 1"
    python_executor = PythonExecutor(py_code, mode="eval", use_pickle=True)

    stdout, stderr = python_executor.run(b"", b"")

    obj = pickle.loads(stdout)
    assert isinstance(stdout, bytes)
    assert isinstance(obj, int)
    assert obj == 2
    assert stderr.decode().strip() == ""


def test_python_executor_eval_pickle_handling_unpickleable_object():
    import pickle

    py_code = "lambda: 1"
    python_executor = PythonExecutor(py_code, mode="eval", use_pickle=True)

    stdout, stderr = python_executor.run(b"", b"")

    assert stderr.decode().strip() != ""

    with pytest.raises(EOFError):
        pickle.loads(stdout)


def test_python_executor_exec_pickle_handling():
    import pickle

    py_code = """
    x = 1
    y = 1

    exec_result = x + y
    """
    python_executor = PythonExecutor(py_code, mode="exec", use_pickle=True)
    stdout, stderr = python_executor.run(b"", b"")

    obj = pickle.loads(stdout)
    assert isinstance(stdout, bytes)
    assert isinstance(obj, int)
    assert obj == 2
    assert stderr.decode().strip() == ""


def test_python_executor_exec_pickle_handling_unpickleable_object():
    import pickle

    py_code = """
    exec_result = lambda: 1
    """
    python_executor = PythonExecutor(py_code, mode="exec", use_pickle=True)
    stdout, stderr = python_executor.run(b"", b"")

    assert stderr.decode().strip() != ""

    with pytest.raises(EOFError):
        pickle.loads(stdout)


def test_python_executor_run_eval_invalid_python_code():
    py_code = "1 + abc"
    python_executor = PythonExecutor(py_code, mode="eval")

    stdout, stderr = python_executor.run(b"", b"")

    assert stdout.decode().strip() == ""
    assert stderr.decode().strip() != ""
    assert stderr.decode().strip() == "name 'abc' is not defined"


def test_python_executor_run_exec_invalid_python_code():
    py_code = """
    x = 1
    y = "abc"

    exec_result = x + y
    """
    python_executor = PythonExecutor(py_code, mode="exec")
    stdout, stderr = python_executor.run(b"", b"")

    assert stdout.decode().strip() == ""
    assert stderr.decode().strip() != ""
    assert stderr.decode().strip() == \
           "unsupported operand type(s) for +: 'int' and 'str'"
