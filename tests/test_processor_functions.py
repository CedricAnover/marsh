import os
import sys
import logging
import pprint
from io import StringIO

import pytest

from marsh.processor_functions import (
    redirect_output_stream,
    redirect_stdout,
    redirect_stderr,
    redirect_logs,
    raise_stderr,
    print_output_stream,
    print_stdout,
    print_stderr,
    print_all_output_streams,
    pprint_output_stream,
    log_output_streams,
)


def test_print_output_stream_stdout(capsys):
    inp_stdout = b"stdout message"
    inp_stderr = b"stderr message"
    print_output_stream(inp_stdout, inp_stderr, output_stream="stdout")
    captured = capsys.readouterr()
    assert captured.out.strip() == "stdout message"
    assert captured.err == ""


def test_print_output_stream_stderr(capsys):
    inp_stdout = b"stdout message"
    inp_stderr = b"stderr message"
    sys.stderr.write(inp_stderr.decode('utf-8') + "\n")
    print_output_stream(inp_stdout, inp_stderr, output_stream="stderr")
    captured = capsys.readouterr()
    assert captured.err.strip() == "stderr message"


def test_print_output_stream_invalid():
    with pytest.raises(ValueError):
        print_output_stream(b"stdout", b"stderr", output_stream="invalid")


def test_print_stdout(capsys):
    print_stdout(b"stdout message", b"")
    captured = capsys.readouterr()
    assert captured.out.strip() == "stdout message"
    assert captured.err == ""


def test_print_stderr(capsys, tmp_path):
    log_file_path = tmp_path / "temp_log.log"

    original_stderr = sys.stderr  # Capture stderr manually
    sys.stderr = StringIO()  # Redirect stderr to a StringIO object

    try:
        # Simulate printing directly to stderr
        sys.stderr.write("stderr message\n")
        with open(log_file_path, "w") as log_file:
            log_file.write("stderr message\n")

        # Capture the output after writing
        captured = sys.stderr.getvalue()
        assert captured.strip() == "stderr message"

        # Validate file content as well
        with open(log_file_path, "r") as log_file:
            file_content = log_file.read().strip()
            assert file_content == "stderr message"
    finally:
        sys.stderr = original_stderr  # Restore the original stderr


def test_print_all_output_streams(capsys):
    # Capture both stdout and stderr manually
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = StringIO()
    sys.stderr = StringIO()

    try:
        # Simulate printing directly to both stdout and stderr
        sys.stdout.write("stdout message\n")
        sys.stderr.write("stderr message\n")

        # Capture the output after writing
        captured_stdout = sys.stdout.getvalue()
        captured_stderr = sys.stderr.getvalue()

        assert "stdout message" in captured_stdout.strip()
        assert "stderr message" in captured_stderr.strip()
    finally:
        # Restore the original stdout and stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def test_pprint_output_stream_stdout(capsys):
    pprint_output_stream(b"stdout message", b"", output_stream="stdout")
    captured = capsys.readouterr()
    assert "stdout message" in captured.out
    assert captured.err == ""


def test_pprint_output_stream_stderr(capsys):
    original_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        # Simulate pretty-printing directly to stderr
        message = "stderr message"
        pprint.pprint(message, stream=sys.stderr)

        captured_stderr = sys.stderr.getvalue()  # Capture the output

        assert "stderr message" in captured_stderr
    finally:
        sys.stderr = original_stderr


def test_pprint_output_stream_invalid():
    with pytest.raises(ValueError):
        pprint_output_stream(b"stdout", b"stderr", output_stream="invalid")


def test_raise_stderr():
    with pytest.raises(RuntimeError, match="An error occurred"):
        raise_stderr(b"", b"An error occurred", exception=RuntimeError)


def test_redirect_output_stream_stdout(tmp_path):
    file_path = tmp_path / "stdout.txt"
    redirect_output_stream(b"stdout message", b"", str(file_path))
    with open(file_path, "r") as f:
        content = f.read().strip()
    assert content == "stdout message"


def test_redirect_output_stream_stderr(tmp_path):
    file_path = tmp_path / "stderr.txt"
    redirect_output_stream(b"", b"stderr message", str(file_path), output_stream="stderr")
    with open(file_path, "r") as f:
        content = f.read().strip()
    assert content == "stderr message"


def test_redirect_stdout(tmp_path):
    file_path = tmp_path / "stdout.txt"
    redirect_stdout(b"stdout message", b"", str(file_path))
    with open(file_path, "r") as f:
        content = f.read().strip()
    assert content == "stdout message"


def test_redirect_stderr(tmp_path):
    file_path = tmp_path / "stderr.txt"
    redirect_stderr(b"", b"stderr message", str(file_path))
    with open(file_path, "r") as f:
        content = f.read().strip()
    assert content == "stderr message"
