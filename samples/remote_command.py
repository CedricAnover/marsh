import sys
import os
import time
import random
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent / "src"
sys.path.append(str(src_path))

from marsh import (
    RemoteCommandExecutor,
    Connector,
    CommandGrammar
)


class ConcreteCommandGrammar(CommandGrammar):
    def build_cmd(self, *commands) -> list[str]:
        return commands


class MockConnection:
    def __init__(self):
        print("Connection Created.")

    def run(self, command: str, use_error=False) -> str:
        print(f"Running Command: {command}")
        if use_error:
            raise Exception("Simulated Exception")
        return command

    def close(self):
        print("Connection Closed.")


class ConcreteConnector(Connector):
    def connect(self) -> MockConnection:
        return MockConnection()

    def disconnect(self, connection: MockConnection):
        connection.close()

    def exec_cmd(self, command: list[str], connection, use_error=False) -> tuple[bytes, bytes]:
        command = " ".join(command)
        mock_cmd_result = connection.run(command, use_error=use_error)
        return mock_cmd_result.encode(), b""


cmd_grammar = ConcreteCommandGrammar()
connector = ConcreteConnector()
cmd_executor = RemoteCommandExecutor(connector, cmd_grammar)
res_stdout, res_stderr = cmd_executor.run(
    b"mock_stdout", b"mock_stderr",
    "/path/to/remote/program", "hello", "world",
    exec_cmd_kwargs=dict(use_error=False)
)

print("STDOUT:", res_stdout.decode())
print("STDERR:", res_stderr.decode())
