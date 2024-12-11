import functools
from dataclasses import dataclass
from typing import Callable, Tuple
from pathlib import Path

from marsh.exceptions import CommandError
from marsh.core.conveyor import Conveyor


@dataclass
class CommandExpression:
    def evaluate(self, *args, **kwargs) -> Tuple[bytes, bytes]:
        raise NotImplementedError("Subclasses of CommandExpression must implement 'evaluate'.")


@dataclass(order=True)
class UnaryExpression(CommandExpression):
    conveyor: Conveyor
    def evaluate(self, *args, **kwargs):
        return self.conveyor(*args, **kwargs)


@dataclass(order=True)
class AndExpression(CommandExpression):
    left: CommandExpression | Conveyor
    right: CommandExpression | Conveyor

    def evaluate(self, *args, **kwargs) -> Tuple[bytes, bytes]:
        # Same as Unix's `command1 && command2`
        # PASS & PASS => PASS
        # PASS & FAIL => FAIL
        # FAIL & NORUN => FAIL
        match self.left:
            case CommandExpression():  # If it's a CommandExpression
                left_stdout, left_stderr = self.left.evaluate(*args, **kwargs)
            case Conveyor():  # If it's a Conveyor
                left_stdout, left_stderr = self.left(*args, **kwargs)
            case _:
                raise ValueError("Invalid type for left side of AndExpression.")

        if left_stderr.decode("utf-8").strip():  # Left expression is a fail
            # Left expression failed
            raise CommandError(left_stderr.decode("utf-8").strip())

        match self.right:
            case CommandExpression():  # If it's a CommandExpression
                right_stdout, right_stderr = self.right.evaluate(x_stdout=left_stdout, x_stderr=left_stderr)
            case Conveyor():  # If it's a Conveyor
                right_stdout, right_stderr = self.right(x_stdout=left_stdout, x_stderr=left_stderr)
            case _:
                raise ValueError("Invalid type for right side of AndExpression.")

        # If right stderr is empty, we pass the stdout from the right side.
        if right_stderr.decode("utf-8").strip():  # Right expression failed
            raise CommandError(right_stderr.decode("utf-8").strip())
        else:
            return right_stdout, right_stderr


@dataclass(order=True)
class OrExpression(CommandExpression):
    left: CommandExpression | Conveyor
    right: CommandExpression | Conveyor

    def evaluate(self, *args, **kwargs) -> Tuple[bytes, bytes]:
        # Same as Unix's `command1 || command2`
        # PASS or NORUN => PASS
        # FAIL or PASS => PASS
        # FAIL or FAIL => FAIL
        match self.left:
            case CommandExpression():  # If it's a CommandExpression
                left_stdout, left_stderr = self.left.evaluate(*args, **kwargs)
            case Conveyor():  # If it's a Conveyor
                left_stdout, left_stderr = self.left(*args, **kwargs)
            case _:
                raise ValueError("Invalid type for left side of AndExpression.")

        # Left expression is a fail
        if left_stderr.decode("utf-8").strip():
            match self.right:
                case CommandExpression():
                    right_stdout, right_stderr = self.right.evaluate(x_stdout=left_stdout, x_stderr=left_stderr)
                case Conveyor():
                    right_stdout, right_stderr = self.right(x_stdout=left_stdout, x_stderr=left_stderr)
                case _:
                    raise ValueError("Invalid type for right side of AndExpression.")

            # Right expression is a fail
            if right_stderr.decode().strip():
                raise CommandError(right_stderr.decode().strip())
            return right_stdout, right_stderr
        # Left expression is a pass
        return left_stdout, left_stderr


@dataclass(order=True)
class JunctionExpression(CommandExpression):
    """
    (command1 > command2) > (command3 > command4)
    
    It may look similar to `command1 & command2` but this does not necessarily raise error if there was an error on left-side.
    """
    left: CommandExpression | Conveyor
    right: CommandExpression | Conveyor

    def evaluate(self, *args, **kwargs) -> Tuple[bytes, bytes]:
        match self.left:
            case CommandExpression():  # If it's a CommandExpression
                left_stdout, left_stderr = self.left.evaluate(*args, **kwargs)
            case Conveyor():  # If it's a Conveyor
                left_stdout, left_stderr = self.left(*args, **kwargs)
            case _:
                raise ValueError("Invalid type for left side of AndExpression.")

        match self.right:
            case CommandExpression():
                right_stdout, right_stderr = self.right.evaluate(x_stdout=left_stdout, x_stderr=left_stderr)
            case Conveyor():
                right_stdout, right_stderr = self.right(x_stdout=left_stdout, x_stderr=left_stderr)
            case _:
                raise ValueError("Invalid type for right side of AndExpression.")
        return right_stdout, right_stderr


class Command:
    def __init__(self, cmd_expr):
        if not isinstance(cmd_expr, (CommandExpression, Conveyor)):
            raise TypeError("The argument for Command constructor must be a CommandExpression or Conveyor.")

        self._cmd_expr = cmd_expr if isinstance(cmd_expr, CommandExpression) else UnaryExpression(cmd_expr)

    @property
    def expression(self) -> CommandExpression:
        return self._cmd_expr

    @classmethod
    def make_junctions(cls, *command_expressions: list[CommandExpression|Conveyor]) -> "Command":
        # new_command = Command.make_junctions(<cmd_expr|cmd_pipe>, <cmd_expr|cmd_pipe>, ...)
        # new_command(...)
        return cls(functools.reduce(JunctionExpression, command_expressions))

    def __or__(self, right: CommandExpression) -> "Command":
        if isinstance(right, CommandExpression):
            return Command(OrExpression(self._cmd_expr, right))
        else:
            return Command(OrExpression(self._cmd_expr, right.expression))

    def __and__(self, right: CommandExpression) -> "Command":
        if isinstance(right, CommandExpression):
            return Command(AndExpression(self._cmd_expr, right))
        else:
            return Command(AndExpression(self._cmd_expr, right.expression))

    def _write_stdout(self, file_path_: str | Path, mode: str) -> None:
        file_path = file_path_ if isinstance(file_path_, Path) else Path(file_path_).resolve()
        stdout, _ = self()
        with file_path.open(mode=mode) as file:
            file.write(stdout.decode("utf-8").strip() + "\n")

    def __gt__(self, right: str | Path) -> None:
        # Write (overwrite) STDOUT to file
        # command > "/path/to/file"
        # command > "/dev/null"

        # Decision: The following evaluates the expression immediately.
        # Warn: We are only considering the STDOUT and not STDERR.
        # command = Command(...)
        # command > "file.txt"

        if isinstance(right, (str, Path)):
            file_path = right if isinstance(right, Path) else Path(right).resolve()
            self._write_stdout(file_path, "w")

        if isinstance(right, Command):
            # Both methods still require pathentesis
            # (command1 > command2) > (command3 > command4)

            # Method: We can achieve Junction without parenthesis using Side-effect
            # self._cmd_expr = JunctionExpression(self._cmd_expr, right.expression)
            # return self

            # Method: Using New Copy
            return Command(JunctionExpression(self._cmd_expr, right.expression))

    def __rshift__(self, right: str | Path) -> None:
        # Append STDOUT to file
        # command >> /path/to/file
        # command >> /dev/null

        # Decision: The following evaluates the expression immediately.
        # Warn: We are only considering the STDOUT and not STDERR.
        # command = Command(...)
        # command >> "file.txt"
        file_path = right if isinstance(right, Path) else Path(right).resolve()
        self._write_stdout(file_path, "a")

    def __call__(self) -> Tuple[bytes, bytes]:
        return self._cmd_expr.evaluate()


__all__ = (
    "CommandExpression",
    "UnaryExpression",
    "AndExpression",
    "OrExpression",
    "JunctionExpression",
    "Command"
)
