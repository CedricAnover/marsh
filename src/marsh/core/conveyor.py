from typing import Callable, Tuple, Sequence

from .cmd_run_decorator import CmdRunDecorator


class Conveyor:
    """
    A class that chains multiple command runners, allowing sequential execution of commands.

    Each command runner is a callable that accepts two `bytes` arguments (representing standard 
    output and standard error) and returns a tuple of two `bytes` values as the updated outputs.

    This class supports adding command runners, decorating them, and invoking them in sequence.
    
    Example:
        >>> def cmd_runner_1(stdout: bytes, stderr: bytes) -> Tuple[bytes, bytes]:
        ...     return stdout + b"Cmd1", stderr

        >>> def cmd_runner_2(stdout: bytes, stderr: bytes) -> Tuple[bytes, bytes]:
        ...     return stdout + b"Cmd2", stderr

        >>> conveyor = Conveyor()
        >>> conveyor = conveyor.add_cmd_runner(cmd_runner_1).add_cmd_runner(cmd_runner_2)
        >>> result_stdout, result_stderr = conveyor(b"Start", b"")
        >>> print(result_stdout)
        b'StartCmd1Cmd2'
    """
    def __init__(self, cmds_=None) -> None:
        self._cmd_runners = cmds_ or []

    @property
    def cmd_run_triples(self) -> Sequence[Tuple[Callable, Tuple, dict]]:
        """
        Returns the sequence of triples containing the registered command runner, its positional arguments and keyword arguments.

        Returns:
            Sequence[Tuple[Callable, Tuple, dict]]: 
                A sequence of command runners with their arguments.
        """
        return self._cmd_runners

    def add_cmd_runner(self,
                cmd_runner: Callable[[bytes, bytes], Tuple[bytes, bytes]],
                *args,
                cmd_runner_decorator: CmdRunDecorator | None = None,
                **kwargs
                ) -> "Conveyor":
        """
        Adds a new command runner to the Conveyor.

        Optionally applies a decorator to the command runner before adding it to the chain.

        Args:
            cmd_runner (Callable[[bytes, bytes], Tuple[bytes, bytes]]): 
                A callable that processes two `bytes` inputs (stdout, stderr) 
                and returns a tuple of two `bytes` outputs.
            *args: 
                Positional arguments to pass to the `cmd_runner` during invocation.
            cmd_runner_decorator (CmdRunDecorator, optional): 
                A command runner decorator for decorating the `cmd_runner`. Defaults to None.
            **kwargs: 
                Keyword arguments to pass to the `cmd_runner` during invocation.

        Returns:
            Conveyor: A new Conveyor instance with the added command runner.

        Raises:
            TypeError: If `cmd_runner` is not callable.
        """
        if not callable(cmd_runner):
            raise TypeError("cmd_runner must be callable with 2 required bytes arguments.")

        # Apply the pre/post processors and modifiers to command runner, if given
        decorated_cmd_runner = cmd_runner_decorator.decorate(cmd_runner) if isinstance(cmd_runner_decorator, CmdRunDecorator) else cmd_runner

        return Conveyor(cmds_=self._cmd_runners + [(decorated_cmd_runner, args, kwargs)])

    def __call__(self, x_stdout: bytes = b"", x_stderr: bytes = b"", callback_list_: Sequence = None) -> Tuple[bytes, bytes]:
        """
        Executes the command runners sequentially.

        Starts with the given `stdout` and `stderr` values and passes the results through
        each command runner in the chain.

        Args:
            x_stdout (bytes, optional): Initial standard output. Defaults to `b""`.
            x_stderr (bytes, optional): Initial standard error. Defaults to `b""`.
            callback_list_ (Sequence, optional): 
                A list of command runners to execute. Defaults to the command runners in the Conveyor.

        Returns:
            Tuple[bytes, bytes]: 
                A tuple containing the final standard output (`stdout`) and standard error (`stderr`).
        """
        callback_list = callback_list_ or self._cmd_runners
        if len(callback_list) == 1:
            callback, args, kwargs = callback_list[0]
            return callback(x_stdout, x_stderr, *args, **kwargs)

        if len(self._cmd_runners) == 0:
            return x_stdout, x_stderr

        callback, args, kwargs = callback_list[0]
        new_x_stdout, new_x_stderr = callback(x_stdout, x_stderr, *args, **kwargs)
        return self(x_stdout=new_x_stdout, x_stderr=new_x_stderr, callback_list_=callback_list[1:])
