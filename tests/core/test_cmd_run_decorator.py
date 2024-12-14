from enum import Enum, auto

import pytest

from marsh import processor_decorator, CmdRunDecorator, stdout_stderr_modifier, add_processors_and_modifiers


#==========================================================================================================
#=========================== Setups
class Invalid(Enum):
    NO_ARGS = auto()
    WRONG_SIGNATURE = auto()
    NO_RETURN_VALUE = auto()  # Technically its `None`
    WRONG_RETURN_VALUE = auto()


@pytest.fixture
def setup_simple_cmd_runner():
    def cmd_runner(stdout: bytes, stderr: bytes):
        return stdout, stderr
    return cmd_runner


@pytest.fixture
def setup_cmd_run_decorator():
    return CmdRunDecorator()


@pytest.fixture
def cmd_runner_with_invalid_arguments(invalid: Invalid):
    if invalid == Invalid.WRONG_SIGNATURE:
        def cmd_runner(x: bytes, k=1):
            return x, k
        return cmd_runner

    if invalid == Invalid.NO_ARGS:
        def cmd_runner():
            return b"", b""
        return cmd_runner


@pytest.fixture
def cmd_runner_with_invalid_return_value(invalid: Invalid):
    if invalid == Invalid.WRONG_RETURN_VALUE:
        def cmd_runner(x_stdout: bytes, x_stderr: bytes):
            return x_stdout + x_stderr
        return cmd_runner

    if invalid == Invalid.NO_RETURN_VALUE:
        def cmd_runner(x_stdout: bytes, x_stderr: bytes):
            pass
        return cmd_runner


@pytest.fixture
def proc_func_with_invalid_arguments(invalid: Invalid):
    if invalid == Invalid.NO_ARGS:
        def proc_func():
            pass

    if invalid == Invalid.WRONG_SIGNATURE:
        def proc_func(x_stdout: bytes, k=2):
            pass
        return proc_func


@pytest.fixture
def mod_func_with_invalid_signature(invalid: Invalid):
    if invalid == Invalid.NO_ARGS:
        def mod_func():
            return b"", b""
        return mod_func

    if invalid == Invalid.WRONG_SIGNATURE:
        def mod_func(inp_stdout: bytes, k=2):
            return inp_stdout, b""
        return mod_func


@pytest.fixture
def mod_func_with_invalid_return_value(invalid: Invalid):
    if invalid == Invalid.WRONG_RETURN_VALUE:
        def mod_func(inp_stdout: bytes, inp_stderr: bytes):
            return inp_stdout + inp_stderr
        return mod_func

    if invalid == Invalid.NO_RETURN_VALUE:
        def mod_func(x_stdout: bytes, x_stderr: bytes):
            pass
        return mod_func


#==========================================================================================================
#=========================== Basic Functionalities and Trivial Cases
def test_processor_decorator(setup_simple_cmd_runner):
    TO_BE_CHANGED = False

    def proc_func(inp_stdout: bytes, inp_stderr: bytes):
        nonlocal TO_BE_CHANGED
        TO_BE_CHANGED = not TO_BE_CHANGED

    # Scenario: before=True
    @processor_decorator(True, proc_func)
    def cmd_runner_before(x_stdout, x_stderr):
        return setup_simple_cmd_runner(x_stdout, x_stderr)
    cmd_runner_before(b"test-stdout", b"test-stderr")
    assert TO_BE_CHANGED is True

    # Scenario: before=False
    @processor_decorator(False, proc_func)
    def cmd_runner_after(x_stdout, x_stderr):
        return setup_simple_cmd_runner(x_stdout, x_stderr)
    cmd_runner_after(b"test-stdout", b"test-stderr")
    assert TO_BE_CHANGED is False


def test_stdout_stderr_modifier(setup_simple_cmd_runner):
    def mod_func(inp_stdout, inp_stderr):
        return b"x", b"y"

    @stdout_stderr_modifier(True, mod_func)
    def cmd_runner_before(x_stdout, x_stderr):
        return setup_simple_cmd_runner(x_stdout, x_stderr)

    stdout, stderr = cmd_runner_before(b"a", b"b")
    assert stdout == b"x" and stderr == b"y"

    @stdout_stderr_modifier(False, mod_func)
    def cmd_runner_after(x_stdout, x_stderr):
        return setup_simple_cmd_runner(x_stdout, x_stderr)

    stdout, stderr = cmd_runner_after(b"a", b"b")
    assert stdout == b"x" and stderr == b"y"


def test_cmd_run_decorator_initialization(setup_cmd_run_decorator):
    cmd_run_decorator = setup_cmd_run_decorator
    assert isinstance(cmd_run_decorator, CmdRunDecorator)
    assert len(cmd_run_decorator._post_processors) == 0
    assert len(cmd_run_decorator._pre_processors) == 0


def test_cmd_run_decorator_add_processor(setup_cmd_run_decorator):
    cmd_run_decorator = setup_cmd_run_decorator
    def f1(x: bytes, y: bytes): pass
    def f2(x: bytes, y: bytes): pass
    def f3(x: bytes, y: bytes): pass
    cmd_run_decorator.add_processor(f1, before=True)
    cmd_run_decorator.add_processor(f2, before=False)
    cmd_run_decorator.add_processor(f3, before=False)
    assert len(cmd_run_decorator._pre_processors) == 1
    assert len(cmd_run_decorator._post_processors) == 2


def test_cmd_run_decorator_add_mod_processor(setup_cmd_run_decorator):
    cmd_run_decorator = setup_cmd_run_decorator
    def f1(x: bytes, y: bytes): return x, y
    def f2(x: bytes, y: bytes): return x, y
    def f3(x: bytes, y: bytes): return x, y
    cmd_run_decorator.add_mod_processor(f1, before=True)
    cmd_run_decorator.add_mod_processor(f2, before=False)
    cmd_run_decorator.add_mod_processor(f3, before=False)
    assert len(cmd_run_decorator._pre_modifiers) == 1
    assert len(cmd_run_decorator._post_modifiers) == 2


def test_cmd_run_decorator_decorate(setup_cmd_run_decorator, setup_simple_cmd_runner):
    cmd_run_decorator = setup_cmd_run_decorator
    cmd_runner = setup_simple_cmd_runner

    TO_BE_CHANGED = False

    def proc_func(inp_stdout, inp_stderr):
        nonlocal TO_BE_CHANGED
        TO_BE_CHANGED = not TO_BE_CHANGED

    def mod_func(inp_stdout, inp_stderr):
        return b"x", b"y"

    cmd_run_decorator.add_processor(proc_func, before=True)
    cmd_run_decorator.add_mod_processor(mod_func, before=False)
    decorated_cmd_runner = cmd_run_decorator.decorate(cmd_runner)

    stdout, stderr = decorated_cmd_runner(b"", b"")

    assert TO_BE_CHANGED is True
    assert stdout == b"x" and stderr == b"y"


def test_add_processors_and_modifiers():
    TO_BE_CHANGED = False
    def proc_func(inp_stdout, inp_stderr):
        nonlocal TO_BE_CHANGED
        TO_BE_CHANGED = not TO_BE_CHANGED

    def mod_func(inp_stdout, inp_stderr):
        return b"x", b"y"

    @add_processors_and_modifiers(
        ("proc", True, proc_func),
        ("mod", False, mod_func),
    )
    def cmd_runner(x_stdout, x_stderr):
        return x_stdout, x_stderr

    stdout, stderr = cmd_runner(b"", b"")
    assert TO_BE_CHANGED is True
    assert stdout == b"x" and stderr == b"y"

#==========================================================================================================
#=========================== Edge Cases and Special Cases

def test_processor_decorator_with_invalid_processor_signature():
    with pytest.raises((TypeError, ValueError)):
        @processor_decorator(True, lambda: None)  # No arguments
        def cmd_runner(x_stdout, x_stderr):
            return x_stdout, x_stderr
        cmd_runner(b"stdout", b"stderr")

        @processor_decorator(True, lambda x: x)  # Invalid Signature
        def cmd_runner(x_stdout, x_stderr):
            return x_stdout, x_stderr
        cmd_runner(b"stdout", b"stderr")


def test_stdout_stderr_modifier_with_invalid_modifier_signature():
    with pytest.raises(ValueError):
        def invalid_modifier(): pass  # Modifier must accept two arguments

        @stdout_stderr_modifier(True, invalid_modifier)
        def cmd_runner(x_stdout, x_stderr):
            return x_stdout, x_stderr
        cmd_runner(b"stdout", b"stderr")


def test_stdout_stderr_modifier_with_invalid_return_value():
    def invalid_modifier(inp_stdout, inp_stderr):
        return inp_stdout + inp_stderr  # Wrong return: not a tuple

    with pytest.raises(ValueError):  # Assuming the code validates output types
        @stdout_stderr_modifier(True, invalid_modifier)
        def cmd_runner(x_stdout, x_stderr):
            return x_stdout, x_stderr
        cmd_runner(b"stdout", b"stderr")


def test_cmd_run_decorator_add_processor_with_modifier(setup_cmd_run_decorator, setup_simple_cmd_runner):
    cmd_run_decorator = setup_cmd_run_decorator
    cmd_runner = setup_simple_cmd_runner

    def valid_processor(x_stdout, x_stderr): pass

    with pytest.raises(TypeError):  # Processors cannot be used as modifiers
        cmd_run_decorator.add_mod_processor(valid_processor, before=True)
        decorated_cmd_runner = cmd_run_decorator.decorate(cmd_runner)
        decorated_cmd_runner(b"", b"")


def test_cmd_run_decorator_decorate_with_invalid_cmd_runner_arguments(setup_cmd_run_decorator):
    cmd_run_decorator = setup_cmd_run_decorator

    # Invalid Signature
    with pytest.raises(TypeError):
        def invalid_cmd_runner(): pass  # Missing required arguments
        decorated_cmd_runner = cmd_run_decorator.decorate(invalid_cmd_runner)
        decorated_cmd_runner(b"", b"")


def test_cmd_run_decorator_decorate_with_invalid_cmd_runner_return_value(setup_cmd_run_decorator):
    cmd_run_decorator = setup_cmd_run_decorator

    def post_proc(inp_stdout, inp_stderr):
        print(inp_stdout, inp_stderr)

    with pytest.raises(ValueError):
        def invalid_return_cmd_runner(x_stdout, x_stderr):
            return x_stdout + x_stderr  # Not a tuple
        cmd_run_decorator.add_processor(post_proc, before=False)  # This should raise error as it requires (<bytes>, <bytes>)
        decorated_cmd_runner = cmd_run_decorator.decorate(invalid_return_cmd_runner)
        decorated_cmd_runner(b"stdout", b"stderr")


def test_add_processors_and_modifiers_with_multiple_processors_and_modifiers_in_mixed_order():
    execution_order = []

    def proc_func_1(x_stdout, x_stderr):
        execution_order.append("proc1")

    def mod_func_1(x_stdout, x_stderr):
        execution_order.append("mod1")
        return x_stdout + b"1", x_stderr

    def proc_func_2(x_stdout, x_stderr):
        execution_order.append("proc2")

    def mod_func_2(x_stdout, x_stderr):
        execution_order.append("mod2")
        return x_stdout, x_stderr + b"2"

    @add_processors_and_modifiers(
        ("proc", True, proc_func_1),
        ("mod", False, mod_func_1),
        ("proc", False, proc_func_2),
        ("mod", True, mod_func_2),
    )
    def cmd_runner(x_stdout, x_stderr):
        return x_stdout, x_stderr

    stdout, stderr = cmd_runner(b"stdout", b"stderr")

    assert execution_order == ["mod2", "proc1", "mod1", "proc2"]
    assert stdout == b"stdout1"
    assert stderr == b"stderr2"
