from abc import abstractmethod, ABC
from marsh.utils import deprecated

# Reference: https://docs.python.org/3.11/library/shlex.html#shlex.split
class CommandGrammar(ABC):
    """
    Abstract base class for defining the structure and behavior of program command grammars.

    This class enforces a consistent interface for defining a program's executable path, 
    its options (e.g., flags or configuration switches), and its arguments. It also provides 
    a mechanism to build the final command to be executed (for subprocess.Popen).

    Methods:
        - build_cmd: Constructs the full command as a list of strings.
    """
    @abstractmethod
    def build_cmd(self, *args, **kwargs) -> list[str]:
        """
        Constructs the full command as a list of strings.

        This method combines the program path, options, and arguments into a single list
        that can be passed to a command-execution library such as `subprocess.Popen`.

        Args:
            *args: Additional arguments to include in the command.
            **kwargs: Additional keyword arguments to customize the command-building process.

        Returns:
            list[str]: The full command to be passed to subprocess.Popen.

        Example:
            ```python
            def build_cmd(self, *args, **kwargs):
                return [self.program_path] + self.options + self.program_args
            ```
        """
        pass
