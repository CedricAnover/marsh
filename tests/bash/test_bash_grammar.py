import pytest

from marsh.bash import BashGrammar


@pytest.fixture
def setup_bash_grammar_no_params():
    return BashGrammar()


@pytest.fixture
def setup_bash_grammar_arbitrary_params():
    return BashGrammar(
        bash_path="/path/to/bash",
        bash_options=["--option1=value1", "--option2=value2"],
        bash_args=["arg1", "arg2"]
    )


def test_bash_grammar_instantiation(setup_bash_grammar_no_params):
    bash_grammar = setup_bash_grammar_no_params
    assert isinstance(bash_grammar, BashGrammar)
    assert isinstance(bash_grammar._bash_path, str)
    assert isinstance(bash_grammar._options, list) and len(bash_grammar._options) == 0
    assert isinstance(bash_grammar._args, list) and len(bash_grammar._args) == 0


def test_bash_grammar_properties(setup_bash_grammar_arbitrary_params):
    bash_grammar = setup_bash_grammar_arbitrary_params
    assert bash_grammar.program_path == "/path/to/bash"
    assert bash_grammar.options == ["--option1=value1", "--option2=value2"]
    assert bash_grammar.program_args == ["arg1", "arg2"]


def test_bash_grammar_add_option(setup_bash_grammar_arbitrary_params):
    bash_grammar = setup_bash_grammar_arbitrary_params
    new_bash_grammar = bash_grammar.add_option("--option3=value3")  # Immutable Pipeline style
    assert new_bash_grammar.options == ["--option1=value1", "--option2=value2", "--option3=value3"]


def test_bash_grammar_add_arg(setup_bash_grammar_arbitrary_params):
    bash_grammar = setup_bash_grammar_arbitrary_params
    new_bash_grammar = bash_grammar.add_arg("arg3")
    assert new_bash_grammar.program_args == ["arg1", "arg2", "arg3"]


def test_bash_grammar_build_cmd(setup_bash_grammar_arbitrary_params):
    bash_grammar = setup_bash_grammar_arbitrary_params
    cmd = bash_grammar.build_cmd()
    assert isinstance(cmd, list)
    assert cmd == ["/path/to/bash", "--option1=value1", "--option2=value2", "arg1 arg2"]
