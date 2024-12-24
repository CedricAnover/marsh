import functools
from typing import Callable

from marsh.core import LocalCommandExecutor
from marsh.bash import BashGrammar
from marsh.bash import BashScript


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

    def create_multi_line_command_grammar(self, commands: list[str], bash_path="bash", bash_options=None, *bash_script_args, **bash_script_kwargs) -> BashGrammar:
        """Creates a BashGrammar from multi-line bash commands.

        Args:
            commands (list[str]): List of bash command to be run sequentially.
            bash_path (str, optional): Path to bash program. Defaults to "bash".
            bash_options (list[str] | None, optional): Options or Flags to be passed to the bash. Defaults to None.

        Returns:
            BashGrammar: Customized BashGrammar instance for multi-line bash commands.
        """
        bash_script = BashScript(*bash_script_args, **bash_script_kwargs)
        bash_options = bash_options or ["-c"]
        script_str: str = bash_script.generate(*commands)
        return BashGrammar(bash_path=bash_path, bash_options=bash_options, bash_args=[script_str])

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
