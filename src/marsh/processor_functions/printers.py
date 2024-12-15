def print_output_stream(inp_stdout: bytes, 
                        inp_stderr: bytes,
                        *args,
                        output_stream="stdout",
                        encoding='utf-8',
                        **kwargs
                        ) -> None:
    if output_stream not in ["stdout", "stderr"]:
        raise ValueError("Output stream must be 'stdout' or 'stderr'.")

    if output_stream == "stdout":
        if inp_stdout.strip():
            print(inp_stdout.decode(encoding).strip(), *args, **kwargs)
    else:
        if inp_stderr.strip():
            print(inp_stderr.decode(encoding).strip(), *args, **kwargs)


def print_stdout(inp_stdout: bytes, inp_stderr: bytes, *args, encoding='utf-8', **kwargs) -> None:
    print_output_stream(inp_stdout, inp_stderr, *args, output_stream="stdout", encoding=encoding, **kwargs)


def print_stderr(inp_stdout: bytes, inp_stderr: bytes, *args, encoding='utf-8', **kwargs) -> None:
    print_output_stream(inp_stdout, inp_stderr, *args, output_stream="stderr", encoding=encoding, **kwargs)


def print_all_output_streams(inp_stdout: bytes, inp_stderr: bytes, *args, encoding='utf-8', **kwargs) -> None:
    print_stdout(inp_stdout, inp_stderr, *args, encoding=encoding, **kwargs)
    print_stderr(inp_stdout, inp_stderr, *args, encoding=encoding, **kwargs)


__all__ = (
    "print_output_stream",
    "print_stdout",
    "print_stderr",
    "print_all_output_streams"
)
