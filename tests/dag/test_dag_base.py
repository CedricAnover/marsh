import pytest

from marsh import Conveyor
from marsh.dag import Dag, Node


class MockConveyor(Conveyor):
    def __init__(self):
        super().__init__()

    def __call__(self, *args, **kwargs):
        return b"stdout", b"stderr"


@pytest.fixture
def setup_dag():
    return Dag("test_dag")


def test_dag_initialization(setup_dag):
    dag = setup_dag
    assert dag.name == "test_dag"
    assert dag.startables == []
    assert dag.graph == {}


def test_dag_add_node(setup_dag):
    dag = setup_dag
    conveyor = MockConveyor()
    node = Node("A", conveyor)
    dag.add(node)
    assert dag.startables == [node]
    assert dag.graph == {"A": set()}


def test_dag_add_node_with_dependencies(setup_dag):
    dag = setup_dag
    conveyor = MockConveyor()
    node_a = Node("A", conveyor)
    node_b = Node("B", conveyor)
    dag.add(node_b, node_a)
    assert dag.startables == [node_b, node_a]
    assert dag.graph == {"A": set(), "B": {"A"}}


def test_dag_remove_node(setup_dag):
    dag = setup_dag
    conveyor = MockConveyor()
    node = Node("A", conveyor)
    dag.add(node)
    dag.remove(node)
    assert dag.startables == []
    assert dag.graph == {}


def test_dag_then_chaining(setup_dag):
    dag = setup_dag
    conveyor = MockConveyor()
    node_a = Node("A", conveyor)
    node_b = Node("B", conveyor)
    dag.do(node_a).then(node_b)
    assert dag.startables == [node_a, node_b]
    assert dag.graph == {"A": set(), "B": {"A"}}


def test_dag_when_dependency(setup_dag):
    dag = setup_dag
    conveyor = MockConveyor()
    node_a = Node("A", conveyor)
    node_b = Node("B", conveyor)
    dag.do(node_a).when(node_b)
    assert dag.startables == [node_a, node_b]
    assert dag.graph == {"A": {"B"}, "B": set()}


def test_dag_then_and_when_chaining(setup_dag):
    dag = setup_dag
    conveyor = MockConveyor()
    node_a = Node("A", conveyor)
    node_b = Node("B", conveyor)
    node_c = Node("C", conveyor)
    dag.do(node_a).then(node_b).when(node_c)
    assert dag.startables == [node_a, node_b, node_c]
    assert dag.graph == {"B": {"A", "C"}, "C": set(), "A": set()}


def test_dag_reset(setup_dag):
    dag = setup_dag
    conveyor = MockConveyor()
    node = Node("A", conveyor)
    dag.add(node)
    dag.reset()
    assert dag.startables == []
    assert dag.graph == {}


def test_dag_sorted_names(setup_dag):
    dag = setup_dag
    conveyor = MockConveyor()
    node_a = Node("A", conveyor)
    node_b = Node("B", conveyor)
    node_c = Node("C", conveyor)
    dag.add(node_a).then(node_b).then(node_c)
    assert dag.sorted_names == ["A", "B", "C"]
