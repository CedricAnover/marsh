import pytest

from marsh.core import Conveyor


@pytest.fixture
def initialize_conveyor():
    conveyor = Conveyor()
    return conveyor


@pytest.fixture
def initialize_conveyor_with_multiple_cmd_runners():
    def f1(x_stdout, x_stderr):
        return b"f1", b""

    def f2(x_stdout, x_stderr):
        return b"f2", b""

    def f3(x_stdout, x_stderr):
        return b"STDOUT", b"STDERR"

    conveyor = Conveyor()\
        .add_cmd_runner(f1)\
        .add_cmd_runner(f2)\
        .add_cmd_runner(f3)
    return conveyor


def test_conveyor_instantiation(initialize_conveyor):
    conveyor = initialize_conveyor
    assert isinstance(conveyor, Conveyor)


def test_cmd_run_triples_property(initialize_conveyor_with_multiple_cmd_runners):
    conveyor = initialize_conveyor_with_multiple_cmd_runners
    assert len(conveyor.cmd_run_triples) == 3
    for tup in conveyor.cmd_run_triples:
        assert callable(tup[0])


def test_add_cmd_runner():
    def f1(x_stdout, x_stderr):
        return b"f1", b""
    conveyor = Conveyor().add_cmd_runner(f1)
    assert len(conveyor.cmd_run_triples) == 1
    func, _, _ = conveyor.cmd_run_triples[0]
    assert func == f1


def test_call(initialize_conveyor_with_multiple_cmd_runners):
    conveyor = initialize_conveyor_with_multiple_cmd_runners
    stdout, stderr = conveyor()
    assert isinstance(stdout, bytes)
    assert isinstance(stderr, bytes)
    assert stdout.decode() == "STDOUT"
    assert stderr.decode() == "STDERR"


def test_empty_conveyor_call():
    conveyor = Conveyor()
    stdout, stderr = conveyor(b"initial stdout", b"initial stderr")
    assert stdout == b"initial stdout"
    assert stderr == b"initial stderr"


def test_cmd_runner_with_empty_output():
    def cmd_runner_with_empty_output(x_stdout, x_stderr):
        return b"", b""
    conveyor = Conveyor().add_cmd_runner(cmd_runner_with_empty_output)
    stdout, stderr = conveyor(b"input stdout", b"input stderr")
    assert stdout == b""
    assert stderr == b""


def test_multiple_cmd_runners_with_empty_output():
    def f1(x_stdout, x_stderr):
        return b"", b""

    def f2(x_stdout, x_stderr):
        return b"", b""

    conveyor = Conveyor().add_cmd_runner(f1).add_cmd_runner(f2)
    stdout, stderr = conveyor(b"initial stdout", b"initial stderr")
    assert stdout == b""
    assert stderr == b""


def test_add_cmd_runner_with_args():
    def cmd_runner_with_args(x_stdout, x_stderr, extra_message):
        return x_stdout + extra_message, x_stderr

    conveyor = Conveyor().add_cmd_runner(cmd_runner_with_args, b" extra")
    stdout, stderr = conveyor(b"start", b"error")
    assert stdout == b"start extra"
    assert stderr == b"error"


def test_add_non_callable_cmd_runner():
    with pytest.raises(TypeError):
        Conveyor().add_cmd_runner("not a function")


def test_call_with_initial_empty_bytes():
    def cmd_runner(x_stdout, x_stderr):
        return b"filled stdout", b"filled stderr"

    conveyor = Conveyor().add_cmd_runner(cmd_runner)
    stdout, stderr = conveyor(b"", b"")
    assert stdout == b"filled stdout"
    assert stderr == b"filled stderr"


def test_multiple_cmd_runners_with_partial_outputs():
    def f1(x_stdout, x_stderr):
        return x_stdout + b" f1", x_stderr

    def f2(x_stdout, x_stderr):
        return x_stdout, x_stderr + b" f2"

    conveyor = Conveyor().add_cmd_runner(f1).add_cmd_runner(f2)
    stdout, stderr = conveyor(b"start", b"start_err")
    assert stdout == b"start f1"
    assert stderr == b"start_err f2"


def test_conveyor_immutability():
    def f1(x_stdout, x_stderr):
        return b"f1", b""

    original_conveyor = Conveyor()
    new_conveyor = original_conveyor.add_cmd_runner(f1)

    assert len(original_conveyor.cmd_run_triples) == 0  # Original should remain empty
    assert len(new_conveyor.cmd_run_triples) == 1


def test_long_chain_of_cmd_runners():
    def make_cmd_runner(index):
        def cmd_runner(x_stdout, x_stderr):
            return x_stdout + f" {index}".encode(), x_stderr
        return cmd_runner

    conveyor = Conveyor()
    for i in range(100):
        conveyor = conveyor.add_cmd_runner(make_cmd_runner(i))

    stdout, stderr = conveyor(b"start", b"")
    assert stdout.startswith(b"start")
    assert stdout.count(b" ") == 100  # Ensure all 100 runners added


def test_cmd_runner_with_exception():
    def faulty_cmd_runner(x_stdout, x_stderr):
        raise ValueError("Simulated failure")

    conveyor = Conveyor().add_cmd_runner(faulty_cmd_runner)
    with pytest.raises(ValueError, match="Simulated failure"):
        conveyor(b"input", b"error")


def test_conveyor_with_mixed_outputs():
    def f1(x_stdout, x_stderr):
        return b"stdout1", x_stderr

    def f2(x_stdout, x_stderr):
        return x_stdout, b"stderr2"

    def f3(x_stdout, x_stderr):
        return x_stdout + b" final", x_stderr + b" final"

    conveyor = Conveyor().add_cmd_runner(f1).add_cmd_runner(f2).add_cmd_runner(f3)
    stdout, stderr = conveyor(b"init", b"init_err")
    assert stdout == b"stdout1 final"
    assert stderr == b"stderr2 final"
