from typing import Callable
from marsh import CmdRunDecorator
from marsh.pre_post_processors import *


def raise_and_print(cmd_runner: Callable[[bytes, bytes], tuple[bytes, bytes]], decorate_now: bool = True) -> Callable | CmdRunDecorator:
    # Pre-Processor
    cmd_run_decorator = CmdRunDecorator()\
        .add_processor(raise_stderr, before=True)\
        .add_processor(print_out_stream, before=True)
    return cmd_run_decorator.decorate(cmd_runner) if decorate_now else cmd_run_decorator


def print_all_output_streams(cmd_runner: Callable, decorate_now: bool = True) -> Callable | CmdRunDecorator:
    # Post-Processor
    cmd_run_decorator = CmdRunDecorator().add_processor(print_all_out_streams, before=False)
    return cmd_run_decorator.decorate(cmd_runner) if decorate_now else cmd_run_decorator


def redirect_stdout(cmd_runner: Callable, file_path: str, decorate_now: bool = True, **proc_kwags) -> Callable | CmdRunDecorator:
    # Post-Processor
    cmd_run_decorator = CmdRunDecorator()\
        .add_processor(redirect_outstream,
                       before=False,
                       proc_args=(file_path,),
                       proc_kwags=proc_kwags
                       )
    return cmd_run_decorator.decorate(cmd_runner) if decorate_now else cmd_run_decorator


def redirect_stderr(cmd_runner: Callable, file_path: str) -> Callable:
    # Post-Processor

    # For a parameterized function such as this, using functools.partial might be required.
    # Example:
    # import functools
    # redirect_stderr_partial = functools.partial(redirect_stderr, "/path/to/file")
    return CmdRunDecorator()\
        .add_processor(redirect_outstream,
                       before=False,
                       proc_args=(file_path,),
                       proc_kwags=dict(out_stream="stderr"))\
        .decorate(cmd_runner)
