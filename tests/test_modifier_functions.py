import pytest

from marsh.modifier_functions import case_conversion, read_file


@pytest.mark.parametrize(
    ("upper", "expected"),
    [(True, b"HELLO"), (False, b"hello")],
)
def test_case_conversion_changes_only_selected_stdout(upper, expected):
    assert case_conversion(b"HeLlO", b"ERR", upper=upper, output_stream="stdout") == (
        expected,
        b"ERR",
    )


@pytest.mark.parametrize(
    ("upper", "expected"),
    [(True, b"ERROR"), (False, b"error")],
)
def test_case_conversion_changes_only_selected_stderr(upper, expected):
    assert case_conversion(b"OUT", b"ErRoR", upper=upper, output_stream="stderr") == (
        b"OUT",
        expected,
    )


def test_case_conversion_handles_empty_streams():
    assert case_conversion(b"", b"", upper=True) == (b"", b"")
    assert case_conversion(b"", b"", upper=False, output_stream="stderr") == (b"", b"")


def test_case_conversion_rejects_invalid_output_stream():
    with pytest.raises(ValueError, match="stdout.*stderr"):
        case_conversion(b"out", b"err", output_stream="invalid")


def test_case_conversion_preserves_binary_bytes_without_decoding():
    value = bytes([0, 255, 97])

    assert case_conversion(value, b"err", upper=True) == (b"\x00\xffA", b"err")


def test_read_file_returns_empty_error_for_empty_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("")

    assert read_file(b"", b"", str(path)) == (b"", b"")


def test_read_file_returns_utf8_content(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("héllo 世界", encoding="utf-8")

    assert read_file(b"", b"", str(path)) == ("héllo 世界".encode("utf-8"), b"")


def test_read_file_returns_error_for_missing_file(tmp_path):
    stdout, stderr = read_file(b"", b"", str(tmp_path / "missing.txt"))

    assert stdout == b""
    assert stderr
    assert b"missing.txt" in stderr


def test_read_file_returns_error_for_directory(tmp_path):
    stdout, stderr = read_file(b"", b"", str(tmp_path))

    assert stdout == b""
    assert stderr


def test_read_file_reports_output_encoding_errors(tmp_path):
    path = tmp_path / "unicode.txt"
    path.write_text("héllo", encoding="utf-8")

    stdout, stderr = read_file(b"", b"", str(path), encoding="ascii")

    assert stdout == b""
    assert b"ascii" in stderr
