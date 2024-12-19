from typing import Optional

from marsh import CommandGrammar


class SshCommandGrammar(CommandGrammar):
    """
    SSH Command Grammar for building SSH commands.
    """
    def build_cmd(self,
                  commands: list[str],
                  prev_stdout: Optional[bytes] = None,
                  *pipe_args,
                  **pipe_kwargs,
                  ) -> list[str]:
        if prev_stdout:
            return commands + [self._pipe_stdout(prev_stdout, *pipe_args, **pipe_kwargs)]
        return commands

    @staticmethod
    def _pipe_stdout(stdout: str | bytes, encoding: str = "utf-8") -> str:
        return rf"""<<'EOF'
{stdout if isinstance(stdout, str) else stdout.decode(encoding)}
EOF
"""
