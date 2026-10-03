from marsh.modifier_functions import case_conversion, read_file


def test_case_conversion_preserves_the_non_selected_stream():
    assert case_conversion(b"hello", b"ERR", upper=True, output_stream="stdout") == (
        b"HELLO",
        b"ERR",
    )
    assert case_conversion(b"OUT", b"hello", upper=False, output_stream="stderr") == (
        b"OUT",
        b"hello",
    )


def test_case_conversion_rejects_invalid_output_stream():
    try:
        case_conversion(b"", b"", output_stream="invalid")
    except ValueError as exc:
        assert "stdout" in str(exc)
    else:
        raise AssertionError("invalid output stream must raise ValueError")


def test_read_file_returns_content_and_empty_stderr(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("hello")

    assert read_file(b"", b"", str(path)) == (b"hello", b"")
