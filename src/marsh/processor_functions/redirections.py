def redirect_output_stream(inp_stdout: bytes,
                           inp_stderr: bytes,
                           file_path: str,
                           output_stream="stdout",
                           mode='w', 
                           encoding='utf-8',
                           ) -> None:
    if output_stream not in ["stdout", "stderr"]:
        raise ValueError("Output stream must be 'stdout' or 'stderr'.")

    with open(file_path, mode) as file:
        if output_stream == "stdout":
            file.write(inp_stdout.decode(encoding).strip())
        else:
            file.write(inp_stderr.decode(encoding).strip())


def redirect_stdout(inp_stdout: bytes,
                    inp_stderr: bytes,
                    file_path: str,
                    mode='w',
                    encoding='utf-8') -> None:
    redirect_output_stream(inp_stdout, inp_stderr, file_path, output_stream="stdout", mode=mode, encoding=encoding)


def redirect_stderr(inp_stdout: bytes,
                    inp_stderr: bytes,
                    file_path: str,
                    mode='w',
                    encoding='utf-8'
                    ) -> None:
    redirect_output_stream(inp_stdout, inp_stderr, file_path, output_stream="stderr", mode=mode, encoding=encoding)


__all__ = (
    "redirect_output_stream",
    "redirect_stdout",
    "redirect_stderr",
)
