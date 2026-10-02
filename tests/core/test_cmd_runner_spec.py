import pytest

from marsh.core import CmdRunDecorator, CmdRunnerSpec


def dummy_runner(x_stdout: bytes, x_stderr: bytes) -> tuple[bytes, bytes]:
    return x_stdout, x_stderr


# --- construction & defaults ---


def test_spec_defaults():
    spec = CmdRunnerSpec(dummy_runner)

    assert spec.cmd_runner is dummy_runner
    assert spec.args == ()
    assert spec.kwargs == {}
    assert spec.decorator is None


def test_spec_is_frozen():
    spec = CmdRunnerSpec(dummy_runner)

    with pytest.raises(AttributeError):
        spec.args = (b"x",)


# --- coerce: identity ---


def test_coerce_identity():
    spec = CmdRunnerSpec(dummy_runner, args=(b"a",), kwargs={"k": b"v"})

    assert CmdRunnerSpec.coerce(spec) is spec


# --- coerce: tuple shapes ---


def test_coerce_bare_runner():
    spec = CmdRunnerSpec.coerce((dummy_runner,))

    assert spec.cmd_runner is dummy_runner
    assert spec.args == ()
    assert spec.kwargs == {}
    assert spec.decorator is None


def test_coerce_with_args():
    spec = CmdRunnerSpec.coerce((dummy_runner, (b"a", b"b")))

    assert spec.args == (b"a", b"b")


def test_coerce_with_kwargs():
    spec = CmdRunnerSpec.coerce((dummy_runner, {"k": b"v"}))

    assert spec.kwargs == {"k": b"v"}


def test_coerce_with_decorator():
    decorator = CmdRunDecorator()
    spec = CmdRunnerSpec.coerce((dummy_runner, decorator))

    assert spec.decorator is decorator


def test_coerce_with_args_and_kwargs():
    spec = CmdRunnerSpec.coerce((dummy_runner, (b"a",), {"k": b"v"}))

    assert spec.args == (b"a",)
    assert spec.kwargs == {"k": b"v"}


def test_coerce_with_args_and_decorator():
    decorator = CmdRunDecorator()
    spec = CmdRunnerSpec.coerce((dummy_runner, (b"a",), decorator))

    assert spec.args == (b"a",)
    assert spec.decorator is decorator


def test_coerce_with_kwargs_and_decorator():
    decorator = CmdRunDecorator()
    spec = CmdRunnerSpec.coerce((dummy_runner, {"k": b"v"}, decorator))

    assert spec.kwargs == {"k": b"v"}
    assert spec.decorator is decorator


def test_coerce_full():
    decorator = CmdRunDecorator()
    spec = CmdRunnerSpec.coerce((dummy_runner, (b"a",), {"k": b"v"}, decorator))

    assert spec.args == (b"a",)
    assert spec.kwargs == {"k": b"v"}
    assert spec.decorator is decorator


# --- coerce: invalid inputs ---


def test_coerce_empty_tuple_raises():
    with pytest.raises(TypeError):
        CmdRunnerSpec.coerce(())


def test_coerce_non_tuple_raises():
    with pytest.raises(TypeError):
        CmdRunnerSpec.coerce("not a tuple")


def test_coerce_non_callable_first_raises():
    with pytest.raises(TypeError):
        CmdRunnerSpec.coerce(("not callable",))


def test_coerce_unexpected_element_raises():
    with pytest.raises(TypeError):
        CmdRunnerSpec.coerce((dummy_runner, 42))


def test_coerce_duplicate_args_raises():
    with pytest.raises(TypeError):
        CmdRunnerSpec.coerce((dummy_runner, (b"a",), (b"b",)))


def test_coerce_duplicate_kwargs_raises():
    with pytest.raises(TypeError):
        CmdRunnerSpec.coerce((dummy_runner, {"a": b"1"}, {"b": b"2"}))
