import functools
from copy import deepcopy
from string import Template
from typing import Callable, Tuple

from marsh.core import Conveyor, LocalCommandExecutor, CmdRunDecorator, EnvCwdRelayExecutor
from marsh.bash.bash_grammar import BashGrammar
from marsh.bash.bash_config import BashConfig


def generate_bash_script(*statements: list[str],
                         shebang: str = "#!/usr/bin/env bash",
                         strict_mode: str = "set -eu -o pipefail",
                         sep: str = "\n\n",
                         **kwargs
                         ) -> str:
    """
    Generates a Bash script as a string from a list of statements.

    Args:
        statements (list[str]): A list of Bash commands to include in the script.
        shebang (str, optional): Shebang line at the top of the script. Defaults to "#!/usr/bin/env bash".
        strict_mode (str, optional): Strict mode options for Bash. Defaults to "set -eu -o pipefail".
        sep (str, optional): Separator to be used between commands. Defaults to "\\n\\n".
        **kwargs: Additional arguments to pass to the Template for dynamic substitution.

    Returns:
        str: The generated Bash script as a string.
    """
    # Example Usage:
    # generate_bash_script("echo 1", "echo 2")
    bash_template_str = fr"""{shebang}

{strict_mode}

$statements_
"""
    bash_template = Template(bash_template_str)
    return bash_template.safe_substitute(
        statements_=f"{sep}".join(statements),
        **kwargs
    )


def create_bash_cmd_runner(command: str, *args, bash_options: list[str] | None = None, pipe_prev_stdout: bool = False, **kwargs) -> Callable[[bytes, bytes], Tuple[bytes, bytes]]:
    """
    Creates a Bash command runner function that can be executed with specific arguments.

    Args:
        command (str): The bash command to run.
        bash_options (list[str] | None, optional): List of Bash options. Defaults to None.
        pipe_prev_stdout (bool, optional): Whether to pipe the previous command's stdout into this one. Defaults to False.
        **kwargs: Additional keyword arguments to pass to the executor.

    Returns:
        Callable[[bytes, bytes], Tuple[bytes, bytes]]: A function that runs the command and returns the output as a tuple.
    """
    # Example Usage:
    # bash_conveyor_belt = BashConveyorBelt(...)
    # bash_conveyor_belt.add_cmd(create_bash_cmd_runner("command", ...), ...)
    # bash_conveyor_belt.add_cmd(create_bash_cmd_runner("command", ...), ...)
    # bash_conveyor_belt.add_cmd(create_bash_cmd_runner("command", ...), ...)
    # ...
    # bash_conveyor_belt.run(...)

    bash_options = bash_options or ["-c"]

    # Create customized BashGrammar
    bash_grammar = BashGrammar(
        bash_path="bash",
        bash_options=bash_options,
        bash_args=[command],
    )

    # Create a LocalCommandExecutor with the BashGrammar instance
    local_cmd = LocalCommandExecutor(bash_grammar, pipe_prev_stdout=pipe_prev_stdout)
    return functools.partial(local_cmd.run, *args, **kwargs)


class BashConveyorBelt:
    """A class that manages the execution of multiple Bash commands sequentially, with global options."""
    def __init__(self, *global_args, **global_kwargs) -> None:
        self._global_args = global_args
        self._global_kwargs = global_kwargs

        # This will not inherit Conveyor. It will use composition over inheritance.
        self.conveyor = Conveyor()

    def reset(self) -> None:
        """
        Resets the conveyor belt, clearing all previously added commands.
        """
        self.conveyor = Conveyor()

    def add_cmd(self, bash_cmd_runner: Callable, *args, cmd_run_decorator: CmdRunDecorator | None = None, **kwargs) -> None:
        """
        Adds a Bash command runner to the conveyor, with the option to override global arguments and keyword arguments.

        Args:
            bash_cmd_runner (Callable): The Bash command runner function to add.
            *args: Additional arguments to pass to the command runner.
            cmd_run_decorator (CmdRunDecorator | None, optional): A decorator to apply to the command runner. Defaults to None.
            **kwargs: Additional keyword arguments to override global options for this command.
        """
        # Create a copy of the global kwargss
        cb_kwargs = deepcopy(self._global_kwargs)

        # Explicitly override global values with provided kwargs
        for key, value in kwargs.items():
            # Ensure critical keys are handled
            if key in cb_kwargs.keys() and key not in ["env"]:
                cb_kwargs[key] = value

            # Handle Environment Variables `env` and ensure that the cmd_runner's specific env keys would override some keys in self._global_kwargs["env"] 
            if key == "env":
                cmd_runner_env = value
                assert isinstance(cmd_runner_env, dict), "cmd_runner_env is not a dictionary."
                global_env = cb_kwargs.get("env", None)
                if global_env:
                    assert isinstance(global_env, dict), "global_env is not a dictionary."
                    # Key-Value Pair from `cmd_runner_env` should override the Key-Value Pair in `global_env` only if the keys are the same.
                    cb_kwargs["env"].update(cmd_runner_env)

        # Apply CmdRunDecorator.decorate() if given as parameter
        bash_cmd_runner = cmd_run_decorator.decorate(bash_cmd_runner) if cmd_run_decorator else bash_cmd_runner

        # Update Conveyor (Side-Effect) with new command runner
        self.conveyor = self.conveyor.add_cmd_runner(
            bash_cmd_runner,
            *(args + self._global_args),
            **cb_kwargs
        )

    def add_one_command(self,
                        command: str,
                        *args,
                        bash_options=None,
                        pipe_prev_stdout=False,
                        cmd_run_decorator: CmdRunDecorator | None = None,
                        **kwargs
                        ) -> None:
        """
        Adds a single Bash command to the conveyor.

        Args:
            command (str): The Bash command to add.
            *args: Additional arguments to pass to the command runner.
            bash_options (optional): Options to pass to Bash. Defaults to None.
            pipe_prev_stdout (bool, optional): Whether to pipe the previous command's stdout into this one. Defaults to False.
            cmd_run_decorator (CmdRunDecorator | None, optional): A decorator for the command. Defaults to None.
            **kwargs: Additional keyword arguments to pass to the command runner.
        """
        self.add_cmd(
            create_bash_cmd_runner(command, bash_options=bash_options, pipe_prev_stdout=pipe_prev_stdout),
            *args,
            cmd_run_decorator=cmd_run_decorator,
            **kwargs
        )

    def add_multi_line_cmd(self,
                           commands: list[str],
                           *args,
                           bash_options=None,
                           pipe_prev_stdout=False,
                           cmd_run_decorator: CmdRunDecorator | None = None,
                           bash_script_args=(),
                           bash_script_kwargs=None,
                           **kwargs) -> None:
        """
        Adds multiple Bash commands (in the form of a script) to the conveyor.

        Args:
            commands (list[str]): List of Bash commands to run sequentially.
            *args: Additional arguments to pass to the command runner.
            bash_options (optional): Options to pass to Bash. Defaults to None.
            pipe_prev_stdout (bool, optional): Whether to pipe the previous command's stdout into this one. Defaults to False.
            cmd_run_decorator (CmdRunDecorator | None, optional): A decorator for the command. Defaults to None.
            bash_script_args (tuple, optional): Arguments to include in the script. Defaults to an empty tuple.
            bash_script_kwargs (dict, optional): Keyword arguments to pass to the script. Defaults to None.
            **kwargs: Additional keyword arguments to pass to the command runner.
        """
        bash_script_kwargs = bash_script_kwargs or dict()
        bash_script_args = [*commands, *bash_script_args]
        bash_script = generate_bash_script(*bash_script_args, **bash_script_kwargs)
        self.add_cmd(
            create_bash_cmd_runner(bash_script, bash_options=bash_options, pipe_prev_stdout=pipe_prev_stdout),
            *args,
            cmd_run_decorator=cmd_run_decorator,
            **kwargs
        )

    def run(self, *args, **kwargs) -> tuple[bytes, bytes]:
        """
        Executes all the commands in the conveyor and returns their output.

        Args:
            *args: Positional arguments to pass to the conveyor's run method.
            **kwargs: Keyword arguments to pass to the conveyor's run method.

        Returns:
            tuple[bytes, bytes]: The output (stdout, stderr) from the execution of the commands.
        """
        return self.conveyor(*args, **kwargs)


class BashFactory:
    """
    A factory class that simplifies the creation of various Bash-related objects, such as command grammars and executors.
    """
    def create_one_command_grammar(self, command: str, bash_path: str="bash", bash_options: list[str] | None = None) -> BashGrammar:
        """Creates a BashGrammar from one-line bash command.

        Args:
            command (str): Bash one-line command.
            bash_path (str, optional): Path to bash program.  Defaults to "bash".
            bash_options (list[str] | None, optional): Options or Flags to be passed to the bash. Defaults to None.

        Returns:
            BashGrammar: Customized BashGrammar instance for one-line bash command.
        """
        bash_options = bash_options or ["-c"]
        return BashGrammar(bash_path=bash_path, bash_options=bash_options, bash_args=[command])

    def create_multi_line_command_grammar(self, commands: list[str], *script_args, bash_path="bash", bash_options=None, **script_kwargs) -> BashGrammar:
        """Creates a BashGrammar from multi-line bash commands.

        Args:
            commands (list[str]): List of bash command to be run sequentially.
            bash_path (str, optional): Path to bash program. Defaults to "bash".
            bash_options (list[str] | None, optional): Options or Flags to be passed to the bash. Defaults to None.

        Returns:
            BashGrammar: Customized BashGrammar instance for multi-line bash commands.
        """
        bash_options = bash_options or ["-c"]
        script_args = [*commands, *script_args]
        bash_script: str = generate_bash_script(*script_args, **script_kwargs)
        return BashGrammar(bash_path=bash_path, bash_options=bash_options, bash_args=[bash_script])

    def create_local_command_executor(self, command: str | list[str], *executor_args, grammar_args=(), grammar_kwargs=None, **executor_kwargs) -> LocalCommandExecutor:
        """Creates a LocalCommandExecutor from one-line or multi-line command.

        Args:
            command (str | list[str]): One-line bash command as string or multi-line commands as a list of strings.
            grammar_args (tuple, optional): Positional arguments for be passed on to the bash grammar factory method. Defaults to ().
            grammar_kwargs (dict, optional): Keyword arguments for be passed on to the bash grammar factory method. Defaults to None.

        Returns:
            LocalCommandExecutor: Customized LocalCommandExecutor.
        """
        grammar_kwargs = grammar_kwargs or dict()
        if isinstance(command, str):
            cmd_grammar = self.create_one_command_grammar(command, *grammar_args, **grammar_kwargs)
        if isinstance(command, list):
            cmd_grammar = self.create_multi_line_command_grammar(command, *grammar_args, **grammar_kwargs)
        return LocalCommandExecutor(cmd_grammar, *executor_args, **executor_kwargs)

    def create_cmd_runner(self, command: str | list[str], *runner_args, executor_args=(), executor_kwargs=None, **runner_kwargs) -> Callable[[bytes, bytes], tuple[bytes, bytes]]:
        """Creates a command runner function from a given command(s) and other factory method parameters.

        Args:
            command (str | list[str]): One-line bash command as string or multi-line commands as a list of strings.
            executor_args (tuple, optional): Positional arguments for be passed on to `create_local_command_executor()`. Defaults to ().
            executor_kwargs (dict, optional): Keyword arguments for be passed on to `create_local_command_executor()`. Defaults to None.

        Returns:
            Callable[[bytes, bytes], tuple[bytes, bytes]]: Customized bash command runner ready to be called, this function can be further enhanced with command runner decorators.
        """
        executor_kwargs = executor_kwargs or dict()
        local_cmd = self.create_local_command_executor(command, *executor_args, **executor_kwargs)
        return functools.partial(local_cmd.run, *runner_args, **runner_kwargs)


class BashUnixPipes(BashConveyorBelt):
    """
    A subclass of BashConveyorBelt that automatically sets pipe_prev_stdout=True for all commands.
    """
    # This class only makes pipe_prev_stdout=True by default
    def add_one_command(self, command, *args, bash_options=None, pipe_prev_stdout=True, cmd_run_decorator = None, **kwargs):
        return super().add_one_command(command, *args, bash_options=bash_options, pipe_prev_stdout=pipe_prev_stdout, cmd_run_decorator=cmd_run_decorator, **kwargs)

    def add_multi_line_cmd(self, commands, *args, bash_options=None, pipe_prev_stdout=True, cmd_run_decorator = None, bash_script_args=(), bash_script_kwargs=None, **kwargs):
        return \
            super().add_multi_line_cmd(
                commands,
                *args,
                bash_options=bash_options,
                pipe_prev_stdout=pipe_prev_stdout,
                cmd_run_decorator=cmd_run_decorator,
                bash_script_args=bash_script_args,
                bash_script_kwargs=bash_script_kwargs,
                **kwargs
            )


__all__ = (
    "generate_bash_script",
    "create_bash_cmd_runner",
    "BashConveyorBelt",
    "BashUnixPipes",
    "BashFactory"
)
