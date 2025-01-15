import logging

from ..utils.output_streams import mask_sensitive_data
from ..logger import create_rotating_file_logger


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


def redirect_logs(inp_stdout: bytes,
                  inp_stderr: bytes,
                  log_file_path: str,
                  name: str = "FileLogger",
                  encoding: str = 'utf-8',
                  sensitive_patterns: list[str] | None = None,
                  **logger_kwargs) -> None:
    logger = create_rotating_file_logger(
        logger_name=name,
        log_file_path=log_file_path,
        **logger_kwargs
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
    "redirect_output_stream",
    "redirect_stdout",
    "redirect_stderr",
    "redirect_logs",
)
