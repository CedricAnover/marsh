import pytest

from marsh import LocalCommandExecutor
from marsh.bash import BashFactory, BashGrammar


@pytest.fixture
def setup_bash_factory():
    return BashFactory()


def test_bash_factory_instantiation(setup_bash_factory):
    bash_factory = setup_bash_factory
    assert isinstance(bash_factory, BashFactory)


def test_bash_factory_create_one_command_grammar(setup_bash_factory):
    bash_factory = setup_bash_factory
    bash_grammar = bash_factory.create_one_command_grammar("mock_command")
    bash_grammar_cmd = bash_grammar.build_cmd()

    # Based on default values
    assert isinstance(bash_grammar, BashGrammar)
    assert bash_grammar_cmd == ["bash", "-c", "mock_command"]


def test_bash_factory_create_multi_line_command_grammar(setup_bash_factory):
    bash_factory = setup_bash_factory
    bash_grammar = bash_factory.create_multi_line_command_grammar(
        ["mock_command_1", "mock_command_2"]
    )
    bash_grammar_cmd = bash_grammar.build_cmd()

    assert isinstance(bash_grammar, BashGrammar)

    expected_script = "#!/usr/bin/env bash\n\nset -eu -o pipefail\n\nmock_command_1\nmock_command_2"
    assert bash_grammar_cmd == ["bash", "-c", expected_script]


def test_bash_factory_create_local_command_executor(setup_bash_factory):
    bash_factory = setup_bash_factory
    cmd_executor = bash_factory.create_local_command_executor("mock_command")
    assert isinstance(cmd_executor, LocalCommandExecutor)
    assert isinstance(cmd_executor.command_grammar, BashGrammar)
    assert cmd_executor.pipe_prev_stdout is False
    assert cmd_executor.timeout is None


def test_bash_factory_create_local_command_executor_multiple_commands(setup_bash_factory):
    bash_factory = setup_bash_factory
    cmd_executor = bash_factory.create_local_command_executor(["mock_command_1", "mock_command_2"])
    assert isinstance(cmd_executor, LocalCommandExecutor)
    assert isinstance(cmd_executor.command_grammar, BashGrammar)
    assert cmd_executor.pipe_prev_stdout is False
    assert cmd_executor.timeout is None


def test_bash_factory_create_cmd_runner(setup_bash_factory):
    bash_factory = setup_bash_factory
    cmd_runner = bash_factory.create_cmd_runner("mock_command")
    assert callable(cmd_runner)


def test_bash_factory_create_cmd_runner_multiple_commands(setup_bash_factory):
    bash_factory = setup_bash_factory
    cmd_runner = bash_factory.create_cmd_runner(["mock_command_1", "mock_command_2"])
    assert callable(cmd_runner)
