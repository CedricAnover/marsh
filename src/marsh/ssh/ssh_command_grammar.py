from typing import Optional

from marsh import CommandGrammar


class SshCommandGrammar(CommandGrammar):
    """
    SSH Command Grammar for building SSH commands.
    """
    def build_cmd(self,
                  commands: list[str],
                  prev_stdout: Optional[bytes] = None,
                  encoding="utf-8",
                  ) -> list[str]:
        if prev_stdout:
            return commands + [prev_stdout.decode(encoding).strip()]
        return commands
