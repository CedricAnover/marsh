import json
import subprocess
import sys

from marsh.core.domain import ProcessSpec, Task, Workflow
from marsh.core.identity import execution_id
from marsh.core.serialization import workflow_to_json


def test_execution_identity_survives_process_boundary():
    workflow = Workflow(
        id="cross-process",
        tasks=(
            Task(
                id="run",
                operation=ProcessSpec(executable=sys.executable, arguments=("-c", "print('x')")),
            ),
        ),
    )
    payload = workflow_to_json(workflow)
    expected = execution_id(workflow, policy=workflow.policy)

    code = """
import json
import sys
from marsh.core.identity import execution_id
from marsh.core.serialization import workflow_from_json

workflow = workflow_from_json(sys.stdin.read())
print(json.dumps({"id": execution_id(workflow, policy=workflow.policy)}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)["id"]
    assert observed == expected
