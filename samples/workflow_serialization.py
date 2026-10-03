"""Round-trip a data-oriented workflow through dict and JSON."""

from marsh import (
    workflow_from_dict,
    workflow_from_json,
    workflow_to_dict,
    workflow_to_json,
)


# Serialization is data-oriented. An execution adapter can interpret the operation data.
definition = {
    "id": "portable",
    "inputs": {"environment": "demo"},
    "outputs": {"kind": "text"},
    "tasks": [
        {
            "id": "emit",
            "operation": {"kind": "shell", "command": "echo portable"},
            "metadata": {"owner": "examples"},
        }
    ],
}

workflow = workflow_from_dict(definition)
as_dict = workflow_to_dict(workflow)
as_json = workflow_to_json(workflow)
round_tripped = workflow_from_json(as_json)

print("dict task ids:", [task["id"] for task in as_dict["tasks"]])
print("json:", as_json)
print("round-trip id:", round_tripped.id)
