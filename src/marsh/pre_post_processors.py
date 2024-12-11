from marsh.exceptions import CommandError


def print_out_stream(inp_stdout: bytes, inp_stderr: bytes, *print_args, use_stdout=True, encoding="utf-8", **print_kwds) -> None:
    out_stream = inp_stdout if use_stdout else inp_stderr
    if out_stream.decode(encoding).strip():
        print(out_stream.decode(encoding).strip(), *print_args, **print_kwds)


def print_all_out_streams(inp_stdout: bytes, inp_stderr: bytes, *print_args, encoding="utf-8", **print_kwds) -> None:
    if inp_stdout.decode(encoding).strip():
        print(inp_stdout.decode(encoding).strip(), *print_args, **print_kwds)
    if inp_stderr.decode(encoding).strip():
        print(inp_stderr.decode(encoding).strip(), *print_args, **print_kwds)


def raise_stderr(inp_stdout: bytes, inp_stderr: bytes, encoding="utf-8") -> None:
    if inp_stderr.decode(encoding).strip():
        raise CommandError(inp_stderr.decode(encoding).strip())


def redirect_outstream(inp_stdout: bytes, inp_stderr: bytes, file_path: str, out_stream="stdout", mode='w', encoding="utf-8") -> None:
    if out_stream not in ["stdout", "stderr"]:
        raise ValueError("out_stream must be 'stdout' or 'stderr'.")
    output_stream_str = inp_stderr.decode(encoding).strip() if out_stream=="stderr" else inp_stdout.decode(encoding).strip()
    if output_stream_str:
        with open(file_path, mode=mode) as file:
            file.write(output_stream_str + "\n")
