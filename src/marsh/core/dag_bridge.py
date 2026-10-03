"""Compatibility bridge from Workflow dependencies to the legacy DAG graph.

The bridge is deliberately scheduling-only: it translates the canonical
Workflow dependency relation into the existing DAG representation without
moving execution semantics into the legacy DAG runtime.
"""

from __future__ import annotations

from marsh.core.domain import Workflow
from marsh.dag.dag import SyncDag
from marsh.dag.startable import Startable


class WorkflowDagNode(Startable):
    """No-op legacy DAG node used only to represent a Workflow task."""

    def start(self):
        raise RuntimeError("WorkflowDagNode is a scheduling adapter and is not executable")


def workflow_to_dag(workflow: Workflow) -> SyncDag:
    """Build a legacy SyncDag containing the Workflow's dependency graph."""
    dag = SyncDag(workflow.id)
    nodes = {task.id: WorkflowDagNode(task.id) for task in workflow.tasks}

    for task in workflow.tasks:
        if task.dependencies:
            dag.add(nodes[task.id], *(nodes[name] for name in task.dependencies))
        else:
            dag.do(nodes[task.id])

    return dag
