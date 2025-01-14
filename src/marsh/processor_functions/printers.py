import logging


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


def log_output_streams(inp_stdout: bytes,
                       inp_stderr: bytes,
                       name="ConsoleLogger",
                       log_level=logging.DEBUG,
                       format_="[%(levelname)s] %(asctime)s | %(message)s",
                       encoding='utf-8'
                       ) -> None:
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(format_)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if inp_stderr.strip():
        logger.error(inp_stderr.decode(encoding).strip())

    if inp_stdout.strip():
        logger.info(inp_stdout.decode(encoding).strip())


__all__ = (
    "print_output_stream",
    "print_stdout",
    "print_stderr",
    "print_all_output_streams",
    "log_output_streams"
)
