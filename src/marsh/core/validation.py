"""Boundary and semantic validation for the canonical Workflow IR."""

from __future__ import annotations

from typing import Any, Mapping

from marsh.core.configuration import normalize_workflow
from marsh.core.diagnostics import Diagnostic
from marsh.core.domain import Workflow
from marsh.core.runtime import plan_workflow


def validate_workflow_diagnostics(
    value: Workflow | Mapping[str, Any],
) -> tuple[Diagnostic, ...]:
    """Return deterministic validation diagnostics without executing work."""

    diagnostics: list[Diagnostic] = []

    try:
        workflow = normalize_workflow(value)
    except (TypeError, ValueError, KeyError) as exc:
        message = str(exc)
        code = "INVALID_CONFIGURATION"
        if "unknown dependencies" in message:
            code = "UNKNOWN_DEPENDENCY"
        diagnostics.append(Diagnostic(code=code, message=message))
        return tuple(diagnostics)

    seen_outputs: dict[str, str] = {}
    for task in workflow.tasks:
        for output in task.outputs:
            previous = seen_outputs.get(output)
            if previous is not None:
                diagnostics.append(
                    Diagnostic(
                        code="DUPLICATE_OUTPUT",
                        message=f"output {output!r} is declared by tasks {previous!r} and {task.id!r}",
                        task_id=task.id,
                    )
                )
            else:
                seen_outputs[output] = task.id

    try:
        plan_workflow(workflow)
    except ValueError as exc:
        if "dependency cycle" in str(exc):
            diagnostics.append(
                Diagnostic(
                    code="DEPENDENCY_CYCLE",
                    message="workflow contains a dependency cycle",
                )
            )
        else:
            diagnostics.append(
                Diagnostic(code="INVALID_SEMANTICS", message=str(exc))
            )

    diagnostics.sort(key=lambda item: (item.code, item.task_id or "", item.message))
    return tuple(diagnostics)
