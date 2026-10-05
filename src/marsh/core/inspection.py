"""Provider-independent, read-only semantic inspection for Marsh workflows."""

from __future__ import annotations

from typing import Any

from marsh.core.domain import Workflow
from marsh.core.identity import execution_id
from marsh.core.providers import LocalProvider, ProviderRegistry
from marsh.core.runtime import plan_workflow


def inspect_workflow(
    workflow: Workflow,
    *,
    provider_registry: ProviderRegistry | None = None,
    provider_name: str = "local",
) -> dict[str, Any]:
    """Return a deterministic semantic snapshot without executing work."""

    plan = plan_workflow(workflow)
    registry = provider_registry or ProviderRegistry({"local": LocalProvider()})
    provider = registry.get(provider_name)

    capabilities = sorted(provider.capabilities.values) if provider is not None else []

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
        "identity": {
            "execution_id": execution_id(workflow, policy=workflow.policy),
            "attempt_identity": "assigned-at-execution",
        },
        "lifecycle": {
            "observed": False,
            "status": "not_started",
            "terminal": False,
        },
        "provider": {
            "name": provider_name,
            "available": provider is not None,
            "capabilities": capabilities,
        },
        "process": {
            "observed": False,
            "identity": None,
        },
        "execution": {
            "performed": False,
        },
    }


__all__ = ["inspect_workflow"]
