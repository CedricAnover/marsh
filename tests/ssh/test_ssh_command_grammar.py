import pytest

from marsh.ssh import SshCommandGrammar


@pytest.fixture
def setup_ssh_cmd_grammar():
    return SshCommandGrammar()


def test_ssh_cmd_grammar_initialization(setup_ssh_cmd_grammar):
    ssh_command_grammar = setup_ssh_cmd_grammar
    assert isinstance(ssh_command_grammar, SshCommandGrammar)


def test_build_cmd_without_pipe(setup_ssh_cmd_grammar):
    ssh_command_grammar = setup_ssh_cmd_grammar

    commands = ["echo 'Hello World'"]
    result = ssh_command_grammar.build_cmd(commands)
    assert result == commands


def test_build_cmd_with_pipe(setup_ssh_cmd_grammar):
    # Test when previous stdout is provided
    ssh_command_grammar = setup_ssh_cmd_grammar

    commands = ["echo 'Hello World'"]
    prev_stdout = b"Previous command output"
    result = ssh_command_grammar.build_cmd(commands, prev_stdout)

    expected_output = commands + [ssh_command_grammar._pipe_stdout(prev_stdout)]
    assert result == expected_output


def test_pipe_stdout_with_str_input(setup_ssh_cmd_grammar):
    # Test _pipe_stdout method with a string as input
    ssh_command_grammar = setup_ssh_cmd_grammar
    input_str = "some stdout output"

    result = ssh_command_grammar._pipe_stdout(input_str)

    expected_output = """<<'EOF'
some stdout output
EOF
"""
    assert result == expected_output


def test_pipe_stdout_with_bytes_input(setup_ssh_cmd_grammar):
    # Test _pipe_stdout method with a bytes object as input
    ssh_command_grammar = setup_ssh_cmd_grammar
    input_bytes = b"some stdout output"

    result = ssh_command_grammar._pipe_stdout(input_bytes)

    expected_output = """<<'EOF'
some stdout output
EOF
"""
    assert result == expected_output
