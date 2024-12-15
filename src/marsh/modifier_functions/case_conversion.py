def case_conversion(inp_stdout: bytes,
                    inp_stderr: bytes,
                    upper=True,
                    output_stream="stdout",
                    ) -> tuple[bytes, bytes]:
    if output_stream not in ["stdout", "stderr"]:
        raise ValueError("Output stream must be 'stdout' or 'stderr'.")

    if output_stream == "stdout":
        return inp_stdout.upper() if upper else inp_stdout.lower(), inp_stderr
    else:
        return inp_stderr.upper() if upper else inp_stderr.lower(), inp_stderr


__all__ = (
    "case_conversion",
)
