def test_modern_namespaces_and_legacy_imports_share_the_same_contracts():
    from marsh import Task as TopLevelTask
    from marsh.core import Conveyor
    from marsh.providers import LocalProvider
    from marsh.runtime import execute_workflow, plan_workflow
    from marsh.workflow import Task

    assert Task is TopLevelTask
    assert callable(execute_workflow)
    assert callable(plan_workflow)
    assert LocalProvider().name == "local"
    assert Conveyor is not None


def test_modern_namespace_exports_are_canonical_objects():
    from marsh.core import ProcessSpec, Result
    from marsh.runtime import LocalMachine, SequentialScheduler
    from marsh.workflow import ProcessStatus, Workflow

    assert ProcessSpec is not None
    assert Result is not None
    assert ProcessStatus is not None
    assert Workflow is not None
    assert LocalMachine is not None
    assert SequentialScheduler is not None
