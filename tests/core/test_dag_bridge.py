from marsh.core.dag_bridge import workflow_to_dag
from marsh.core.domain import Task, Workflow


def test_workflow_to_dag_preserves_dependency_graph_and_order():
    workflow = Workflow(
        id="bridge",
        tasks=(
            Task(id="consumer", operation=lambda *_: None, dependencies=("producer",)),
            Task(id="producer", operation=lambda *_: None),
            Task(id="independent", operation=lambda *_: None),
        ),
    )

    dag = workflow_to_dag(workflow)

    assert dag.graph == {
        "consumer": {"producer"},
        "producer": set(),
        "independent": set(),
    }
    assert dag.sorted_names == ["producer", "independent", "consumer"]


def test_workflow_dag_bridge_is_not_an_execution_path():
    workflow = Workflow(
        id="bridge",
        tasks=(Task(id="task", operation=lambda *_: None),),
    )

    node = workflow_to_dag(workflow).startables[0]

    try:
        node.start()
    except RuntimeError as exc:
        assert "scheduling adapter" in str(exc)
    else:
        raise AssertionError("WorkflowDagNode must never execute workflow work")
