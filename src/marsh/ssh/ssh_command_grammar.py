from typing import Optional

from marsh import CommandGrammar


class SshCommandGrammar(CommandGrammar):
    """
    SSH Command Grammar for building SSH commands by adding custom logic.

    Inherits from `CommandGrammar` and provides a method to build commands with 
    optional piping logic.
    """
    def build_cmd(self,
                  commands: list[str],
                  prev_stdout: Optional[bytes] = None,
                  *pipe_args,
                  **pipe_kwargs,
                  ) -> list[str]:
        """
        Builds the full SSH command by optionally piping the stdout of a previous command to the next.

        Args:
            commands (list[str]): The list of commands to execute.
            prev_stdout (Optional[bytes]): The stdout from the previous command to pipe into the current one.
            *pipe_args: Arguments for the piping logic.
            **pipe_kwargs: Keyword arguments for the piping logic.

        Returns:
            list[str]: A list of strings representing the final SSH command with any necessary piping logic.
        """
        if prev_stdout:
            return commands + [self._pipe_stdout(prev_stdout, *pipe_args, **pipe_kwargs)]
        return commands

    @staticmethod
    def _pipe_stdout(stdout: str | bytes, encoding: str = "utf-8") -> str:
        """
        Creates a formatted string to pipe the stdout of a previous command into the next.

        Args:
            stdout (str | bytes): The stdout to be piped.
            encoding (str): The encoding to use if `stdout` is a byte string. Default is "utf-8".

        Returns:
            str: The formatted string to pipe the stdout.
        """
        return rf"""<<'EOF'
{stdout if isinstance(stdout, str) else stdout.decode(encoding)}
EOF
"""
