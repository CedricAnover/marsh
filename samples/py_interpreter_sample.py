from marsh.core.command_grammar import PyCommandGrammar
from marsh import Conveyor, PyInterpreterExecutor

py_code = """
import os
import sys
import shutil

print("x_stdout:", $x_stdout)
print("x_stderr:", $x_stderr)

print("ENV_VAR:", os.getenv("ENV_VAR"))
print("CWD:", os.getcwd())
print("Python:", shutil.which("python"))
"""

# Example: PyInterpreterExecutor
py_interpreter = PyInterpreterExecutor()
stdout, stderr = py_interpreter.run(
    b"Hello",
    b"World",
    py_code,
    env=dict(ENV_VAR="env-var-value")
)

print(stdout.decode().strip())

if stderr.strip():
    print(stderr.decode().strip())

# Example: PyCommandGrammar
py_cmd_grammar = PyCommandGrammar("bash -c", "python -c")
command = py_cmd_grammar.build_cmd(py_code="")
print("COMMAND:", command)
