import multiprocessing
from concurrent.futures import ThreadPoolExecutor

import pytest

from marsh import Conveyor
from marsh.docker import DockerCommandExecutor, DockerCommandGrammar
from marsh.exceptions import DockerError
from .fixtures import _get_container_from_filter, command_executor


def test_instantiation():
    image = "bash:latest"
    docker_command_executor = DockerCommandExecutor(image)
    assert isinstance(docker_command_executor, DockerCommandExecutor)
    assert docker_command_executor._client_args == ()
    assert docker_command_executor._client_kwargs == {}
    assert docker_command_executor._create_args == ()
    assert docker_command_executor._create_kwargs == {}
    assert docker_command_executor._container_name is None
    assert docker_command_executor.image == image
    assert isinstance(docker_command_executor._command_grammar, DockerCommandGrammar)


@pytest.mark.parametrize(
    'command_executor',
    [
        (["bash:latest"], dict(container_name="test_container")),
    ],
    indirect=True
)
def test_docker_cleanup(command_executor):
    command_executor.run(b"", b"", ["echo Hello World"])
    stdout, stderr = _get_container_from_filter("test_container")

    # Assert that the container is removed
    assert stdout == ""
    assert stderr == ""


@pytest.mark.parametrize(
    'command_executor',
    [
        (["bash:latest"], dict()),
    ],
    indirect=True
)
def test_basic_command_without_piping(command_executor):
    command_executor = command_executor
    stdout, stderr = command_executor.run(
        b"mock_x_stdout",
        b"mock_x_stderr",
        ["echo 'Hello World'"]
    )
    assert isinstance(stdout, bytes)
    assert isinstance(stderr, bytes)
    assert stdout.decode().strip() == "Hello World"
    assert stderr.decode().strip() == ""


@pytest.mark.parametrize(
    'command_executor',
    [
        (["bash:latest"], dict(pipe_prev_stdout=True)),
    ],
    indirect=True
)
def test_basic_command_with_piping(command_executor):
    # command_executor = command_executor
    x_stdout = r''
    stdout, stderr = command_executor.run(
        b"Hello World",
        b"",
        ["echo"]
    )
    print(f"STDOUT:", stdout.decode().strip())
    assert isinstance(stdout, bytes)
    assert isinstance(stderr, bytes)
    assert stdout.decode().strip() == "Hello World"
    assert stderr.decode().strip() == ""


def test_chained_multiple_docker_executors():
    # Test how multiple command runners built from `DockerCommandExecutor`
    # would behave along with conveyor.
    command_executor_1 = DockerCommandExecutor("bash:latest", start_timeout=0.1, pipe_prev_stdout=False)
    command_executor_2 = DockerCommandExecutor("bash:latest", start_timeout=0.1, pipe_prev_stdout=True)
    command_executor_3 = DockerCommandExecutor("bash:latest", start_timeout=0.1, pipe_prev_stdout=True)

    conveyor = Conveyor()\
        .add_cmd_runner(command_executor_1.run, "echo World")\
        .add_cmd_runner(command_executor_2.run, "echo Hello") \
        .add_cmd_runner(command_executor_3.run, "echo")

    stdout, stderr = conveyor()
    assert stdout.decode().strip() == "Hello World"
    assert stderr.decode().strip() == ""


@pytest.mark.parametrize(
    'command_executor',
    [
        (["bash:latest"], {}),
    ],
    indirect=True
)
def test_with_none_zero_exit_code(command_executor):
    # Mock and simulate when exist code is non-zero (an error).
    invalid_cmd = "mock_invalid_cmd"
    stdout, stderr = command_executor.run(b"", b"", invalid_cmd)

    # Assert empty stdout and an existing stderr
    assert stdout.decode().strip() == ""
    assert stderr.decode().strip() == f"/bin/sh: {invalid_cmd}: not found"


def test_timeout_handling():
    timeout = 1
    test_timeout = 2.5
    command_executor = DockerCommandExecutor(
        "bash:latest",
        start_timeout=0.01,
        timeout=timeout
    )

    # TODO: Fix and catch the TimeoutError in `DockerCommandExecutor`.
    # with pytest.warns()
    with pytest.raises(TimeoutError):
        command_executor.run(b"", b"", f"sleep {test_timeout}")


def test_non_existent_docker_image():
    command_executor = DockerCommandExecutor("mock_non_existent_image")
    with pytest.raises(DockerError):
        command_executor.run(b"", b"", "echo Testing")


def test_instantiation_with_invalid_client_parameters():
    pass


def test_instantiation_with_invalid_container_constructor_parameters():
    pass


def test_with_invalid_run_keyword_arguments():
    command_executor = DockerCommandExecutor("bash:latest")
    # TODO: Fix - Throw and catch specific error when passing invalid keyword argument
    #  in DockerCommandExecutor.run to Container.exec_run
    with pytest.raises(Exception):
        command_executor.run(b"", b"", "echo Testing", invalid_kwg=2)


@pytest.mark.parametrize(
    'command_executor',
    [
        (["bash:latest"], {}),
    ],
    indirect=True
)
def test_injecting_environment_variable(command_executor):
    stdout, stderr = command_executor.run(
        b"",
        b"",
        'echo "$ENV_VAR_1 $ENV_VAR_2"',
        environment=dict(
            ENV_VAR_1="Hello",
            ENV_VAR_2="World"
        )
    )
    assert stdout.decode().strip() == "Hello World"
    assert stderr.decode().strip() == ""


@pytest.mark.parametrize(
    'command_executor',
    [
        (["bash:latest"], dict(working_dir="/test_dir")),  # Create the work directory in `docker create`
    ],
    indirect=True
)
def test_change_working_directory(command_executor):
    stdout, stderr = command_executor.run(
        b"",
        b"",
        "pwd",
        workdir="/test_dir"
    )

    assert stdout.decode().strip() == "/test_dir"
    assert stderr.decode().strip() == ""
