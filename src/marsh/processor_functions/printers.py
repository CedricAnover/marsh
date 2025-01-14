import pprint
import logging

from ..utils.output_streams import mask_sensitive_data
from ..logger import create_console_logger


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


def pprint_output_stream(inp_stdout: bytes,
                         inp_stderr: bytes,
                         output_stream="stdout",
                         encoding='utf-8',
                         **pprinter_kwargs
                         ) -> None:
    if output_stream not in ["stdout", "stderr"]:
        raise ValueError("Output stream must be 'stdout' or 'stderr'.")

    pprinter = pprint.PrettyPrinter(**pprinter_kwargs)
    if output_stream == "stdout":
        if inp_stdout.strip():
            pprinter.pprint(inp_stdout.decode(encoding).strip())
    else:
        if inp_stderr.strip():
            pprinter.pprint(inp_stderr.decode(encoding).strip())


def log_output_streams(inp_stdout: bytes,
                       inp_stderr: bytes,
                       name="ConsoleLogger",
                       log_level=logging.DEBUG,
                       format_="[%(levelname)s] %(message)s",
                       encoding='utf-8',
                       sensitive_patterns: list[str] | None = None
                       ) -> None:
    logger = create_console_logger(
        logger_name=name,
        format_=format_
    )

    if sensitive_patterns is None:
        sensitive_patterns = []

    if inp_stderr.strip():
        stderr_message = inp_stderr.decode(encoding).strip()
        stderr_message = mask_sensitive_data(stderr_message, sensitive_patterns)
        logger.error(stderr_message)

    if inp_stdout.strip():
        stdout_message = inp_stdout.decode(encoding).strip()
        stdout_message = mask_sensitive_data(stdout_message, sensitive_patterns)
        logger.info(stdout_message)


__all__ = (
    "print_output_stream",
    "print_stdout",
    "print_stderr",
    "print_all_output_streams",
    "pprint_output_stream",
    "log_output_streams"
)
