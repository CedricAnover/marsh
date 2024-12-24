import pytest

from marsh.exceptions import ScriptError
from marsh import Script
from marsh.bash import BashScript


def test_bash_script_subclass():
    assert issubclass(BashScript, Script)


@pytest.fixture
def setup_bash_script():
    bash_script = BashScript()
    return bash_script


def test_bash_script_instantiation(setup_bash_script):
    bash_script = setup_bash_script
    assert isinstance(bash_script, (BashScript, Script))
    assert isinstance(bash_script.script_template, str)


@pytest.fixture(params=[
    ["echo 1", "echo 2"]
])
def setup_2_line_sample(request):
    bash_script = BashScript()
    return bash_script.generate(*request.param)


def test_bash_script_generate(setup_2_line_sample):
    script_str = setup_2_line_sample

    assert isinstance(script_str, str)

    lines = script_str.split("\n")

    assert lines[0] == "#!/usr/bin/env bash"  # Shebang
    assert lines[2] == "set -eu -o pipefail"  # Debugging

    # Remind: Default separator is "\n" in generate
    assert lines[4] == "echo 1"
    assert lines[5] == "echo 2"

    assert len(lines) == 6


def test_bash_script_instantiation_invalid_shebang():
    with pytest.raises(ScriptError):
        BashScript(shebang="/usr/bin/env bash")

    with pytest.raises(ScriptError):
        BashScript(shebang="#/usr/bin/env bash")

    with pytest.raises(ScriptError):
        BashScript(shebang="!/usr/bin/env bash")


def test_bash_script_generate_invalid_input(setup_bash_script):
    bash_script = setup_bash_script

    with pytest.raises(TypeError):
        bash_script.generate(["echo 1", "echo 2"])

    with pytest.raises(TypeError):
        bash_script.generate(("echo 1", "echo 2"))
