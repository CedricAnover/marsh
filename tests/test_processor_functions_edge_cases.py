import logging

import pytest

from marsh.processor_functions import (
    log_output_streams,
    pprint_output_stream,
    print_all_output_streams,
    print_output_stream,
    print_stderr,
    print_stdout,
    raise_stderr,
    redirect_logs,
    redirect_output_stream,
    redirect_stderr,
    redirect_stdout,
)


def test_print_output_stream_ignores_empty_selected_stream(capsys):
    print_output_stream(b"", b"stderr", output_stream="stdout")
    print_output_stream(b"stdout", b"", output_stream="stderr")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize("output_stream", ["stdout", "stderr"])
def test_print_output_stream_accepts_custom_encoding(capsys, output_stream):
    message = "héllo"
    encoded = message.encode("utf-8")

    print_output_stream(encoded, encoded, output_stream=output_stream)

    captured = capsys.readouterr()
    if output_stream == "stdout":
        assert captured.out.strip() == message
        assert captured.err == ""
    else:
        assert captured.out == ""
        assert captured.err.strip() == message


def test_print_stdout_and_stderr_select_only_the_requested_stream(capsys):
    print_stdout(b"out", b"err")
    print_stderr(b"out", b"err")

    captured = capsys.readouterr()
    assert captured.out.strip() == "out"
    assert captured.err.strip() == "err"


def test_print_all_output_streams_emits_both_streams(capsys):
    print_all_output_streams(b"out", b"err")

    captured = capsys.readouterr()
    assert captured.out.strip() == "out"
    assert captured.err.strip() == "err"


@pytest.mark.parametrize("function", [print_output_stream, pprint_output_stream])
def test_output_stream_processors_reject_invalid_stream(function):
    with pytest.raises(ValueError, match="stdout.*stderr"):
        function(b"out", b"err", output_stream="invalid")


def test_pprint_output_stream_accepts_pretty_printer_options(capsys):
    pprint_output_stream(b"hello", b"", output_stream="stdout", width=20)

    captured = capsys.readouterr()
    assert "hello" in captured.out
    assert captured.err == ""


def test_log_output_streams_masks_sensitive_data(caplog):
    name = "test_log_output_streams_masks_sensitive_data"
    with caplog.at_level(logging.DEBUG, logger=name):
        log_output_streams(
            b"user=alice token=secret",
            b"warning token=secret",
            name=name,
            sensitive_patterns=[r"token=\w+"],
        )

    messages = [record.getMessage() for record in caplog.records if record.name == name]
    assert messages == ["warning ***", "user=alice ***"]


def test_redirect_output_stream_writes_selected_stream_and_honors_append_mode(tmp_path):
    path = tmp_path / "output.txt"

    redirect_output_stream(b"first", b"ignored", str(path))
    redirect_output_stream(b"ignored", b"second", str(path), output_stream="stderr", mode="a")

    assert path.read_text() == "firstsecond"


def test_redirect_output_stream_rejects_invalid_stream(tmp_path):
    with pytest.raises(ValueError, match="stdout.*stderr"):
        redirect_output_stream(b"out", b"err", str(tmp_path / "output.txt"), output_stream="invalid")


def test_redirect_stdout_and_stderr_write_their_selected_stream(tmp_path):
    stdout_path = tmp_path / "stdout.txt"
    stderr_path = tmp_path / "stderr.txt"

    redirect_stdout(b"out", b"err", str(stdout_path))
    redirect_stderr(b"out", b"err", str(stderr_path))

    assert stdout_path.read_text() == "out"
    assert stderr_path.read_text() == "err"


def test_redirect_output_stream_honors_encoding(tmp_path):
    path = tmp_path / "output.txt"

    redirect_output_stream("héllo".encode("utf-8"), b"", str(path))

    assert path.read_text(encoding="utf-8") == "héllo"


def test_redirect_logs_writes_masked_messages_to_file(tmp_path):
    path = tmp_path / "marsh.log"

    redirect_logs(
        b"user=alice token=secret",
        b"warning token=secret",
        str(path),
        name="test_redirect_logs_writes_masked_messages_to_file",
        sensitive_patterns=[r"token=\w+"],
    )

    content = path.read_text()
    assert "[ERROR] warning ***" in content
    assert "[INFO] user=alice ***" in content


def test_raise_stderr_raises_only_when_stderr_is_non_empty():
    raise_stderr(b"stdout", b"", RuntimeError)

    with pytest.raises(RuntimeError, match="failure"):
        raise_stderr(b"", b"failure", RuntimeError)


def test_raise_stderr_honors_encoding():
    with pytest.raises(RuntimeError, match="héllo"):
        raise_stderr(b"", "héllo".encode("utf-8"), RuntimeError)
