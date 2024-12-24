from marsh.core import CommandGrammar
from marsh.constants import BASH_PATH


class BashGrammar(CommandGrammar):
    """
    A concrete implementation of the `CommandGrammar` class for constructing and managing Bash commands.

    The `BashGrammar` class simplifies building Bash command-line invocations by providing methods to 
    add options, arguments, inline commands, or scripts. It allows users to create flexible, reusable 
    Bash commands programmatically and can be integrated with other tools that execute shell commands.
    """
    # /path/to/bash [options] [args]
    # /bin/bash -c command
    # /bin/bash /path/to/file
    def __init__(self,
                 bash_path: str | None = BASH_PATH,
                 bash_options: list[str] | None = None,
                 bash_args: list[str] | None =None,
                 ):
        self._bash_path = bash_path or "bash"
        self._options = bash_options or []
        self._args = bash_args or []

    @property
    def program_path(self) -> str:
        return self._bash_path

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def program_args(self) -> list[str]:
        return self._args

    def add_option(self, option: str) -> "BashGrammar":
        return BashGrammar(bash_options=self._options+[option], bash_args=self._args)

    def add_arg(self, arg: str) -> "BashGrammar":
        return BashGrammar(bash_options=self._options, bash_args=self._args+[arg])

    def build_cmd(self) -> list[str]:
        return [self._bash_path, *self._options, " ".join(self._args)]
