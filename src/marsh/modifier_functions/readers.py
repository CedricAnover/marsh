def read_file(inp_stdout: bytes, inp_stderr: bytes, file_path: str, encoding='utf-8') -> tuple[bytes, bytes]:
    try:
        with open(file_path, 'r') as file:
            return file.read().encode(encoding), b""
    except (FileNotFoundError, PermissionError, IsADirectoryError, OSError, UnicodeEncodeError, IOError) as e:
        return b"", str(e).encode(encoding)


__all__ = (
    "read_file",
)
