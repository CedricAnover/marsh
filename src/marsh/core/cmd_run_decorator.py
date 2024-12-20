import functools
import inspect
from typing import Callable


def _is_proc_or_mod_func_args_valid(func: Callable) -> bool:
    # Validate the signature of func
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    if len(params) < 2:  # Check if there are at least two parameters
        return False
    match params[0], params[1]:  # Match first two parameters to check if they are positional and of type bytes
        case (inspect.Parameter(kind=inspect.Parameter.POSITIONAL_OR_KEYWORD), inspect.Parameter(kind=inspect.Parameter.POSITIONAL_OR_KEYWORD)):
            # Validate that they are of type 'bytes'
            if not all(isinstance(param.annotation, type(bytes)) or param.annotation == inspect.Parameter.empty for param in params[:2]):
                return False
        case _:
            return False
    return True


def processor_decorator(before: bool,
                        proc_func: Callable[[bytes, bytes], None],
                        *proc_args,
                        **proc_kwargs
                        ) -> Callable[[bytes, bytes], tuple[bytes, bytes]]:
    """
    A decorator to add pre-processing or post-processing behavior to a command runner function.

    This decorator wraps a command runner function with pre- or post-processing logic. The `before` argument
    specifies whether the processor function (`proc_func`) should run before or after the command runner.

    Args:
        before (bool): If True, the processor runs before the command runner (pre-processing).
                      If False, it runs after the command runner (post-processing).
        proc_func (Callable[[bytes, bytes], None]): The processor function that extends or modifies
                      the behavior of the command runner.
        *proc_args: Additional positional arguments to pass to `proc_func`.
        **proc_kwargs: Additional keyword arguments to pass to `proc_func`.

    Returns:
        Callable[[bytes, bytes], tuple[bytes, bytes]]: A decorated command runner function that includes 
        pre- or post-processing logic.
    """
    if not _is_proc_or_mod_func_args_valid(proc_func):
        raise ValueError("The processor function has invalid signature.")

    def outer(cmd_runner):
        @functools.wraps(cmd_runner)
        def wrapper(x_stdout, x_stderr, *args, **kwargs):
            # Execute processor before or after
            if before:
                proc_func(x_stdout, x_stderr, *proc_args, **proc_kwargs)
                stdout, stderr = cmd_runner(x_stdout, x_stderr, *args, **kwargs)
            else:
                stdout, stderr = cmd_runner(x_stdout, x_stderr, *args, **kwargs)
                proc_func(stdout, stderr, *proc_args, **proc_kwargs)
            return stdout, stderr
        return wrapper
    return outer


def stdout_stderr_modifier(before: bool,
                           mod_func: Callable[[bytes, bytes], tuple[bytes, bytes]],
                           *mod_args,
                           **mod_kwargs
                           ) -> Callable[[bytes, bytes], tuple[bytes, bytes]]:
    """
    A decorator that modifies the standard output and error of a command runner function.

    This decorator allows you to modify the stdout and stderr either before or after the command runner function
    executes. The `mod_func` should return the modified stdout and stderr as a tuple.

    In `processor_decorator()`, the `proc_func` does not return any result, which limits its ability to perform modifications.
    This decorator is primarily suited for use cases such as validation, error handling, printing, logging, notifications, etc.
    In contrast, the `mod_func` allows users to manipulate the `(x_stdout, x_stderr)` or `(stdout, stderr)` values and return the
    modified results. However, it does not modify the arguments in place, as the bytes objects are immutable. Use cases for this
    include data cleaning, ETL (Extract, Transform, Load) processes, and similar tasks.

    Args:
        before (bool): If True, the modifier function is applied to the command's stdout and stderr before
                       the command runner is executed. If False, it is applied after.
        mod_func (Callable[[bytes, bytes], tuple[bytes, bytes]]): A function that modifies the command's stdout and stderr.
        *mod_args: Additional positional arguments passed to `mod_func`.
        **mod_kwargs: Additional keyword arguments passed to `mod_func`.

    Returns:
        Callable[[bytes, bytes], tuple[bytes, bytes]]: A new command runner function that includes the modifications.
    """
    # Validate the Signature of Modifier Function
    if not _is_proc_or_mod_func_args_valid(mod_func):
        raise ValueError("The processor function has invalid signature.")

    def outer(cmd_runner):
        @functools.wraps(cmd_runner)
        def wrapper(x_stdout: bytes, x_stderr: bytes, *args, **kwargs) -> tuple[bytes, bytes]:
            if before:
                # mod_func() will be used to transform the previous command runner's results (bytes, bytes), and use this "modified"
                # results for the current command runner as arguments.
                mod_x_stdout, mod_x_stderr = mod_func(x_stdout, x_stderr, *mod_args, **mod_kwargs)
                mod_stdout, mod_stderr = cmd_runner(mod_x_stdout, mod_x_stderr, *args, **kwargs)
                return mod_stdout, mod_stderr
            else:
                # mod_func() will be used to "modify" the current command runner's result and finally returns the modified results.
                stdout, stderr = cmd_runner(x_stdout, x_stderr, *args, **kwargs)
                mod_stdout, mod_stderr = mod_func(stdout, stderr, *mod_args, **mod_kwargs)
                return mod_stdout, mod_stderr
        return wrapper
    return outer


class CmdRunDecorator:
    """
    A class for managing and applying chains of pre- and post-processors and modifiers to a command runner.

    This class allows you to add processor and modifier functions to a command runner. Processors can be applied
    before or after the command runner, and modifiers modify the stdout and stderr either before or after the runner.
    
    Methods:
        add_processor: Adds a processor function to the pre- or post-processor chain.
        add_mod_processor: Adds a modifier function to the pre- or post-modifier chain.
        decorate: Applies the added processors and modifiers to a command runner function.
    """
    def __init__(self, decorated_runners: list[Callable]=None):
        # Separate chains for processors and modifiers
        self._pre_processors = []
        self._post_processors = []
        self._pre_modifiers = []  # To store mod_func processors to be applied before
        self._post_modifiers = []  # To store mod_func processors to be applied after

        if decorated_runners:
            for runner in decorated_runners:
                if runner["before"]:
                    self._pre_processors.append(runner["decorator"])
                else:
                    self._post_processors.append(runner["decorator"])

    def add_processor(self,
                      processor: Callable[[bytes, bytes], None],
                      before: bool = True,
                      proc_args: tuple = (),
                      proc_kwargs: dict | None = None) -> "CmdRunDecorator":
        """
        Adds a processor function to the pre- or post-processor chain.

        Args:
            processor (Callable[[bytes, bytes], None]): A function to process the command's stdout and stderr.
            before (bool, optional): If True, the processor is added to the pre-processor chain. Defaults to True.
            proc_args (tuple, optional): Positional arguments for the processor. Defaults to ().
            proc_kwargs (dict, optional): Keyword arguments for the processor. Defaults to None.

        Returns:
            CmdRunDecorator: The current CmdRunDecorator instance to allow method chaining.
        """
        proc_kwags_ = proc_kwargs or {}
        cmd_runner_decorator = processor_decorator(before, processor, *proc_args, **proc_kwags_)

        if before:
            self._pre_processors.append(cmd_runner_decorator)
        else:
            self._post_processors.append(cmd_runner_decorator)

        return self

    def add_mod_processor(self,
                          mod_func: Callable[[bytes, bytes], tuple[bytes, bytes]],
                          before: bool = True,
                          mod_args: tuple = (),
                          mod_kwargs: dict | None = None) -> "CmdRunDecorator":
        """
        Adds a modifier function to the pre- or post-modifier chain.

        Args:
            mod_func (Callable[[bytes, bytes], tuple[bytes, bytes]]): A function that modifies the command's stdout and stderr.
            before (bool, optional): If True, the modifier is added to the pre-modifier chain. Defaults to True.
            mod_args (tuple, optional): Positional arguments for the modifier. Defaults to ().
            mod_kwargs (dict, optional): Keyword arguments for the modifier. Defaults to None.

        Returns:
            CmdRunDecorator: The current CmdRunDecorator instance to allow method chaining.
        """
        mod_kwags_ = mod_kwargs or {}
        cmd_runner_decorator = stdout_stderr_modifier(before, mod_func, *mod_args, **mod_kwags_)

        if before:
            self._pre_modifiers.append(cmd_runner_decorator)  # Store pre-modifiers
        else:
            self._post_modifiers.append(cmd_runner_decorator)  # Store post-modifiers

        return self

    def decorate(self, cmd_runner: Callable[[bytes, bytes], tuple[bytes, bytes]]) -> Callable[[bytes, bytes], tuple[bytes, bytes]]:
        """
        Decorates a command runner function with the pre- and post-processors and modifiers.

        The order of evaluation:
            1) Pre-Modifiers
            2) Pre-Processors
            3) Command Runner
            4) Post-Modifiers
            5) Post-Processors

        Args:
            cmd_runner (Callable[[bytes, bytes], tuple[bytes, bytes]]): The command runner function to decorate.

        Returns:
            Callable[[bytes, bytes], tuple[bytes, bytes]]: The decorated command runner function.
        """
        # 2nd
        # Apply pre-processors (before the command runner)
        for pre_processor in reversed(self._pre_processors):  # Reverse order for before-processors
            cmd_runner = pre_processor(cmd_runner)

        # 1st
        # Apply pre-modifiers (before the command runner)
        for pre_modifier in reversed(self._pre_modifiers):  # Reverse order for before-modifiers
            cmd_runner = pre_modifier(cmd_runner)

        # 3rd
        # Apply post-modifiers (after the command runner)
        for post_modifier in self._post_modifiers:
            cmd_runner = post_modifier(cmd_runner)

        # 4th
        # Apply post-processors (after the command runner)
        for post_processor in self._post_processors:
            cmd_runner = post_processor(cmd_runner)

        return cmd_runner


def add_processors_and_modifiers(*tup_list: list[tuple]) -> Callable[[bytes, bytes], tuple[bytes, bytes]]:
    """
    A decorator that allows adding multiple processors and modifiers to a command runner.

    This decorator allows adding both processors and modifiers in one call, either to modify the output
    or to perform additional processing before or after the command execution.

    Args:
        *tup_list (list[tuple]): A list of tuples specifying processors and modifiers. Each tuple must contain
                                  the classification ("proc" or "mod") followed by the appropriate function and arguments.

    Returns:
        Callable[[bytes, bytes], tuple[bytes, bytes]]: A decorated command runner function.
    """
    def outer(cmd_runner):
        @functools.wraps(cmd_runner)
        def wrapper(x_stdout, x_stderr, *args, **kwargs):
            # Initialize the Command Run Decorator
            cmd_runner_decorator = CmdRunDecorator()

            for tup in tup_list:
                assert isinstance(tup, (tuple, list))
                assert isinstance(tup[0], str) and tup[0] in ["proc", "mod"], 'The classifier must be "proc" or "mod".'

                # Classifier ("proc" or "mod")
                proc_or_mod = tup[0]

                # Set the Method for adding either a "processor" or "modifier"
                adder_method = cmd_runner_decorator.add_processor if proc_or_mod == "proc" else cmd_runner_decorator.add_mod_processor

                # Pattern Match on the given tuples
                # Only match the required information and not the classification of "proc" or "mod"
                match tup[1:]:
                    case (before, callback):
                        adder_method(callback, before=before)
                    case (before, callback, args_) if isinstance(args_, (tuple, list)):
                        adder_method(callback, before=before, mod_args=args_) if proc_or_mod == "mod" else adder_method(callback, before=before, proc_args=args_)
                    case (before, callback, kwargs_) if isinstance(kwargs_, dict):
                        adder_method(callback, before=before, mod_kwargs=kwargs_) if proc_or_mod == "mod" else adder_method(callback, before=before, proc_kwargs=kwargs_)
                    case (before, callback, args_, kwargs_) if isinstance(args_, (tuple, list)) and isinstance(kwargs_, dict):
                        adder_method(callback, before=before, mod_args=args_, mod_kwargs=kwargs_) if proc_or_mod == "mod" else adder_method(callback, before=before, proc_args=args_, proc_kwargs=kwargs_)
                    case _:
                        error_message = f"{tup} is invalid."
                        ValueError(error_message)

            # Decorate the command runner
            decorated_cmd_runner = cmd_runner_decorator.decorate(cmd_runner)
            return decorated_cmd_runner(x_stdout, x_stderr, *args, **kwargs)
        return wrapper
    return outer


__all__ = (
    "processor_decorator",
    "stdout_stderr_modifier",
    "CmdRunDecorator",
    "add_processors_and_modifiers"
)
