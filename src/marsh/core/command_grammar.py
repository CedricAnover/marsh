import shlex
from abc import abstractmethod, ABC
from typing import List


# TODO: Utilize shlex.split() for parsing the full command.
# Reference: https://docs.python.org/3.11/library/shlex.html#shlex.split
class CommandGrammar(ABC):
    """
    Abstract base class for defining the structure and behavior of program command grammars.

    This class enforces a consistent interface for defining a program's executable path, 
    its options (e.g., flags or configuration switches), and its arguments. It also provides 
    a mechanism to build the final command to be executed (for subprocess.Popen).

    Properties:
        - program_path (str): The path to the executable program.
        - options (List[str]): A list of options or flags to be passed to the program.
        - program_args (List[str]): A list of arguments for the program.

    Methods:
        - build_cmd: Constructs the full command as a list of strings that can be passed to 
                     `subprocess.Popen` or similar command-executing libraries.
    """

    @abstractmethod
    def build_cmd(self, *args, **kwargs) -> List[str]:
        """
        Constructs the full command as a list of strings.

        This method combines the program path, options, and arguments into a single list
        that can be passed to a command-execution library such as `subprocess.Popen`.

        Args:
            *args: Additional arguments to include in the command.
            **kwargs: Additional keyword arguments to customize the command-building process.

        Returns:
            List[str]: The full command to be passed to subprocess.Popen.

        Example:
            ```python
            def build_cmd(self, *args, **kwargs):
                return [self.program_path] + self.options + self.program_args
            ```
        """
        pass


class PyCommandGrammar(CommandGrammar):
    """
    Class to generate and manage shell commands for Python code execution.

    This class extends `CommandGrammar` to handle building shell commands for running
    Python code. It combines a shell command (e.g., `bash`) with a Python command (e.g.,
    `python3`) and optionally includes Python code. The command can be constructed
    with or without additional quoting and handles special characters in the shell and
    Python code.

    Attributes:
        shell_cmd (str): The shell command (e.g., `bash`, `sh`, etc.) to execute.
        py_cmd (str): The Python command (e.g., `python3`, or a specific Python interpreter).
    """

    def __init__(self, shell_cmd: str, py_cmd: str):
        """
        Initializes the `PyCommandGrammar` instance with the specified shell and Python commands.

        Args:
            shell_cmd (str): The shell command (e.g., `bash`, `sh`, etc.) to execute.
            py_cmd (str): The Python command (e.g., `python3`, or a specific Python interpreter).

        Raises:
            ValueError: If either the shell command or Python command is an empty string.
        """
        # TODO: Add validation to `py_cmd`. Note that this could be absolute or relative path,
        #  global or venv python interpreter, etc.

        if not shell_cmd.strip():
            raise ValueError("The shell command cannot be empty.")

        if not py_cmd.strip():
            raise ValueError("The python command cannot be empty.")

        self.shell_cmd = shell_cmd
        self.py_cmd = py_cmd

    def build_cmd(self,
                  py_code: str = "",
                  comments: bool = False,
                  posix: bool = True,
                  use_shlex_quote: bool = False,
                  ) -> List[str]:
        """
        Constructs the full shell command to execute a Python program with optional arguments.

        This method combines the `shell_cmd` and `py_cmd` along with the provided Python code.
        The Python code can be quoted using `shlex.quote` if `use_shlex_quote` is set to `True`.
        It also supports handling of shell command options and the inclusion of comments in the
        Python code when `comments=True`.

        Args:
            py_code (str, optional): The Python code to be executed. Default is an empty string.
            comments (bool, optional): If `True`, comments in the Python code are preserved.
                                       Default is `False`.
            posix (bool, optional): If `True`, POSIX shell quoting conventions are followed.
                                    Default is `True`.
            use_shlex_quote (bool, optional): If `True`, quotes the Python code using `shlex.quote`.
                                              Default is `False`.

        Returns:
            List[str]: The constructed shell command as a list of strings to be passed to
                       a command execution library such as `subprocess.Popen`.

        Example:
            >>> grammar = PyCommandGrammar(shell_cmd="bash", py_cmd="python3")
            >>> grammar.build_cmd(py_code="print('Hello')")
            ['bash', 'python3', "print('Hello')"]
        """

        # Warning The shlex module is only designed for Unix shells.
        # Reference: https://docs.python.org/3.12/library/shlex.html#:~:text=in%20version%203.8.-,shlex.quote,-(s)

        # Apply shlex quoting to python code if required
        python_code = shlex.quote(py_code) if use_shlex_quote and py_code else py_code

        # Start with shell command and python command
        # Apply shlex quoting to shell and python commands individually if required
        if use_shlex_quote:
            cmd = f"{shlex.quote(self.shell_cmd)} {shlex.quote(self.py_cmd)}"
        else:
            cmd = f"{self.shell_cmd} {self.py_cmd}"

        full_cmd_ls = shlex.split(cmd, comments=comments, posix=posix)

        if python_code:
            full_cmd_ls.append(python_code)

        return full_cmd_ls
