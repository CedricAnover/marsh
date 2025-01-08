import pytest

from marsh.docker import DockerCommandGrammar


def test_init_valid_shell_command():
    grammar = DockerCommandGrammar("/bin/bash -c")
    assert grammar.shell_command == "/bin/bash -c"


def test_init_empty_shell_command():
    with pytest.raises(ValueError, match="The shell command cannot be empty"):
        DockerCommandGrammar("")


@pytest.mark.parametrize(
    "command,expected",
    [
        ("echo hello", ["/bin/sh", "-c", "echo hello"]),
        (["echo", "hello"], ["/bin/sh", "-c", "echo hello"]),
    ],
)
def test_build_cmd_basic(command, expected):
    grammar = DockerCommandGrammar("/bin/sh -c")
    result = grammar.build_cmd(command)
    assert result == expected


@pytest.mark.parametrize(
    "command,x_stdout,expected",
    [
        ("echo hello", " > output.txt", ["/bin/sh", "-c", "echo hello > output.txt"]),
        (["echo", "hello"], " > output.txt", ["/bin/sh", "-c", "echo hello > output.txt"]),
        ("echo hello", b" > output.txt", ["/bin/sh", "-c", "echo hello > output.txt"]),
    ],
)
def test_build_cmd_with_stdout(command, x_stdout, expected):
    grammar = DockerCommandGrammar("/bin/sh -c")
    result = grammar.build_cmd(command, x_stdout)
    assert result == expected


def test_build_cmd_with_bytes_stdout():
    grammar = DockerCommandGrammar("/bin/sh -c")
    result = grammar.build_cmd("echo hello", b" > output.txt")
    assert result == ["/bin/sh", "-c", "echo hello > output.txt"]


def test_build_cmd_empty_command():
    grammar = DockerCommandGrammar("/bin/sh -c")
    result = grammar.build_cmd("")
    assert result == ["/bin/sh", "-c", ""]


def test_pipe_prev_stdout_not_implemented():
    grammar = DockerCommandGrammar("/bin/sh -c")
    with pytest.raises(NotImplementedError):
        grammar.pipe_prev_stdout("some stdout")
