"""Stable, read-only Marsh command-line inspection surface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from marsh import __version__
from marsh.core.serialization import workflow_from_json
from marsh.diagnostics import redact
from marsh.extensions import discover_extensions

EXIT_SUCCESS = 0
EXIT_INVALID = 2
EXIT_INCOMPATIBLE = 3
EXIT_INTERNAL = 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="marsh")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect", help="inspect a workflow without executing it"
    )
    inspect_parser.add_argument("workflow", type=Path)
    inspect_parser.add_argument("--json", action="store_true", dest="machine")

    plugins = subparsers.add_parser("plugins", help="inspect installed extensions")
    plugins.add_argument("action", choices=("list",))
    plugins.add_argument("--json", action="store_true", dest="machine")
    return parser


def _inspect(path: Path) -> dict[str, Any]:
    workflow = workflow_from_json(path.read_text(encoding="utf-8"))
    from marsh.core.identity import execution_id
    from marsh.core.runtime import plan_workflow

    plan = plan_workflow(workflow)
    identity = None
    try:
        identity = execution_id(workflow, policy=workflow.policy)
    except (TypeError, ValueError):
        pass

    return {
        "workflow": {
            "id": workflow.id,
            "task_count": len(workflow.tasks),
            "task_ids": [task.id for task in workflow.tasks],
        },
        "plan": {
            "order": list(plan.order),
            "ready": list(plan.ready),
        },
        "identity": {"execution_id": identity},
        "execution": {"performed": False},
    }


def _print(value: Any, machine: bool) -> None:
    safe = redact(value)
    if machine:
        print(json.dumps(safe, sort_keys=True, separators=(",", ":")))
        return
    if isinstance(safe, dict) and "workflow" in safe:
        workflow = safe["workflow"]
        plan = safe["plan"]
        print(f"Workflow: {workflow['id']}")
        print(f"Tasks: {workflow['task_count']}")
        print(f"Plan: {' -> '.join(plan['order'])}")
        print(f"Ready: {', '.join(plan['ready']) or 'none'}")
        print(f"Execution ID: {safe['identity']['execution_id'] or 'not portable'}")
        print("Execution: not performed")
        return
    for item in safe:
        print(
            f"{item['name']} [{item['status']}]"
            + (f": {item['reason']}" if item["reason"] else "")
        )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "inspect":
            _print(_inspect(args.workflow), args.machine)
            return EXIT_SUCCESS
        if args.command == "plugins":
            items = [item.to_dict() for item in discover_extensions()]
            _print(items, args.machine)
            return (
                EXIT_INCOMPATIBLE
                if any(item["status"] == "unsupported" for item in items)
                else EXIT_SUCCESS
            )
        return EXIT_INVALID
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {redact(str(exc))}", file=sys.stderr)
        return EXIT_INVALID
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print(f"error: {type(exc).__name__}: {redact(str(exc))}", file=sys.stderr)
        return EXIT_INTERNAL


__all__ = [
    "EXIT_INCOMPATIBLE",
    "EXIT_INTERNAL",
    "EXIT_INVALID",
    "EXIT_SUCCESS",
    "main",
]
