import pytest

from marsh.core.command_grammar import PyCommandGrammar


def test_build_cmd_with_code_and_options():
    grammar = PyCommandGrammar(shell_cmd="/bin/bash", py_cmd="python3")
    cmd = grammar.build_cmd(py_code="print('Hello')", posix=False)

    # Expecting the correct command with python code included
    assert cmd == ['/bin/bash', 'python3', "print('Hello')"]


def test_shell_cmd_with_special_characters():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash -x", py_cmd="python3")
    cmd = py_cmd_grammar.build_cmd(py_code="print('Hello')")

    expected_cmd = ['bash', '-x', 'python3', "print('Hello')"]
    assert cmd == expected_cmd


def test_build_cmd_with_spaces_in_code():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash", py_cmd="python3")
    py_code = "print('Hello World')"
    cmd = py_cmd_grammar.build_cmd(py_code=py_code)

    # Expect python code to stay as a single string with single quotes around it
    expected_cmd = ['bash', 'python3', "print('Hello World')"]
    assert cmd == expected_cmd


def test_build_cmd_with_comments_true():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash", py_cmd="python3")
    cmd = py_cmd_grammar.build_cmd(py_code="print('Hello World')  # A Comment", comments=True)

    # The command should include the python code with comments preserved
    expected_cmd = ["bash", "python3", "print('Hello World')  # A Comment"]
    assert cmd == expected_cmd


def test_build_cmd_with_posix_false():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash", py_cmd="python3")
    cmd = py_cmd_grammar.build_cmd(py_code="print('Hello World')", posix=False)

    # Test that posix=False results in proper escaping of the Python code
    expected_cmd = ["bash", "python3", "print('Hello World')"]
    assert cmd == expected_cmd


def test_empty_shell_cmd():
    with pytest.raises(ValueError):
        PyCommandGrammar(shell_cmd="", py_cmd="python3")


def test_empty_py_cmd():
    with pytest.raises(ValueError):
        PyCommandGrammar(shell_cmd="bash", py_cmd="")


def test_shell_cmd_with_special_character_in_shell():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash -i", py_cmd="python3")
    cmd = py_cmd_grammar.build_cmd(py_code="print('Hello')")
    expected_cmd = ['bash', '-i', 'python3', "print('Hello')"]
    assert cmd == expected_cmd


def test_python_code_with_quotes():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash", py_cmd="python3")
    py_code = """print('This is a \\\"quoted\\\" string')"""
    cmd = py_cmd_grammar.build_cmd(py_code=py_code)

    # Ensure that quotes are escaped properly
    expected_cmd = ["bash", "python3", "print('This is a \\\"quoted\\\" string')"]
    assert cmd == expected_cmd


def test_build_cmd_without_code():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash", py_cmd="python3")
    cmd = py_cmd_grammar.build_cmd(py_code="")

    # Ensure the command is built without Python code
    expected_cmd = ["bash", "python3"]
    assert cmd == expected_cmd


def test_valid_shell_and_py_cmd():
    grammar = PyCommandGrammar(shell_cmd="bash", py_cmd="python3")

    # The construction should work without any issue
    cmd = grammar.build_cmd(py_code="print('Hello')")
    expected_cmd = ["bash", "python3", "print('Hello')"]
    assert cmd == expected_cmd


def test_python_code_with_single_and_double_quotes():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash", py_cmd="python3")
    py_code = """print("Hello world with single", 'and double quotes')"""
    cmd = py_cmd_grammar.build_cmd(py_code=py_code)

    # Ensure that Python code with single and double quotes is correctly passed
    expected_cmd = ['bash', 'python3', 'print("Hello world with single", \'and double quotes\')']
    assert cmd == expected_cmd


def test_special_characters_in_shell_and_python_code():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash -i", py_cmd="python3")
    py_code = "print('Hello, World! $USER')"
    cmd = py_cmd_grammar.build_cmd(py_code=py_code)

    # Ensure that shell command and python code with special characters are handled properly
    expected_cmd = ['bash', '-i', 'python3', "print('Hello, World! $USER')"]
    assert cmd == expected_cmd


def test_python_code_with_special_characters_and_shlex_quote():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash", py_cmd="python3")
    py_code = """print('This is a "quoted" string with spaces')"""
    cmd = py_cmd_grammar.build_cmd(py_code=py_code, use_shlex_quote=True)

    # Ensure the python code is properly quoted
    expected_cmd = ['bash', 'python3', '\'print(\'"\'"\'This is a "quoted" string with spaces\'"\'"\')\'']
    assert cmd == expected_cmd


def test_shell_cmd_with_options_and_python_code():
    py_cmd_grammar = PyCommandGrammar(shell_cmd="bash -x -i", py_cmd="python3")
    py_code = "print('Debugging!')"
    cmd = py_cmd_grammar.build_cmd(py_code=py_code)

    # Ensure the shell command options and Python code are combined properly
    expected_cmd = ['bash', '-x', '-i', 'python3', "print('Debugging!')"]
    assert cmd == expected_cmd
