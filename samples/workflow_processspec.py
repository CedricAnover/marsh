"""Exercise ProcessSpec inputs such as environment, stdin, cwd, and metadata."""

import os
import sys
import tempfile
from pathlib import Path

from marsh import ProcessSpec, Task, Workflow, execute_workflow


with tempfile.TemporaryDirectory() as directory:
    workdir = Path(directory)
    workflow = Workflow(
        id="process-spec",
        tasks=(
            Task(
                id="inspect",
                operation=ProcessSpec(
                    executable=sys.executable,
                    arguments=(
                        "-c",
                        "import os, pathlib, sys; "
                        "print(os.environ['MARSH_MODE']); "
                        "print(pathlib.Path('.').resolve()); "
                        "print(sys.stdin.read())",
                    ),
                    environment={"MARSH_MODE": "example"},
                    working_directory=os.fspath(workdir),
                    stdin=b"hello stdin",
                    metadata={"purpose": "process-spec-demo"},
                ),
            ),
        ),
    )

    result = execute_workflow(workflow)["inspect"]

if not result.ok:
    raise RuntimeError(result.error)

print(result.stdout.decode().strip())
