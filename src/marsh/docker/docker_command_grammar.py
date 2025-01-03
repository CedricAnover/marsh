from marsh import CommandGrammar


class DockerCommandGrammar(CommandGrammar):
    def __init__(self, shell_command: str = "/bin/sh -c"):
        if not shell_command.strip():
            raise ValueError("The shell command cannot be empty. Example: Use '/bin/sh -c'")
        self.shell_command = shell_command

    def build_cmd(self,
                  command: str | list[str],
                  x_stdout: str | bytes | None = None
                  ) -> list[str]:
        shell_command = self.shell_command.split()

        x_stdout = x_stdout.decode() if isinstance(x_stdout, bytes)\
            else x_stdout if isinstance(x_stdout, str)\
            else None

        if isinstance(command, str):
            full_command = [*shell_command, command]
        else:
            full_command = [*shell_command, " ".join(command)]

        if x_stdout:
            full_command[-1] = full_command[-1] + " " + x_stdout.strip()

        return full_command

    def pipe_prev_stdout(self, x_stdout: str | bytes) -> list[str]:
        pass
