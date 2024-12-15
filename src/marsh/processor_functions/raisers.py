def raise_stderr(inp_stdout: bytes, inp_stderr: bytes, exception: type[Exception], *args, encoding='utf-8', **kwargs) -> None:
    if inp_stderr.strip():
        raise exception(inp_stderr.decode(encoding).strip(), *args, **kwargs)


__all__ = (
    "raise_stderr",
)
