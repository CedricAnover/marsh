from graphlib import TopologicalSorter, CycleError

import pytest

from marsh import Conveyor
from marsh.dag import (
    Node,
    Dag,
    SyncDag,
    AsyncDag,
    ThreadPoolDag,
    ThreadDag,
    MultiprocessDag,
    ProcessPoolDag
)


def mock_cmd_runner(x_stdout: bytes, x_stderr: bytes, name: str):
    return f"{name}-stdout".encode(), f"{name}-stderr".encode()


@pytest.fixture
def setup_nodes():
    def _create_node(name: str) -> Node:
        return Node(name, Conveyor().add_cmd_runner(mock_cmd_runner, name))

    return {
        letter.upper(): _create_node(letter.upper())
        for letter in ["a", "b", "c", "d", "e", "f", "g"]
    }


@pytest.fixture(params=[SyncDag, AsyncDag, ThreadPoolDag, ThreadDag, MultiprocessDag, ProcessPoolDag])
def setup_dag_kind(request):
    return request.param


@pytest.fixture
def setup_dag(setup_dag_kind, setup_nodes):
    dag_kind = setup_dag_kind
    nodes: dict[str, Node] = setup_nodes

    # Instantiate the Dag with their default constructor parameters and give name
    dag = dag_kind(f"Mock-{dag_kind.__name__}")

    # Define the node dependencies
    dag.do(nodes["A"]).then(nodes["C"], nodes["D"], nodes["F"], nodes["G"])
    dag.do(nodes["B"]).then(nodes["D"], nodes["E"])
    dag.do(nodes["C"]).then(nodes["G"])
    dag.do(nodes["D"]).then(nodes["F"])
    dag.do(nodes["E"]).then(nodes["G"])

    return dag


@pytest.fixture
def setup_expected_results():
    return {
        "A": (b"A-stdout", b"A-stderr"),
        "B": (b"B-stdout", b"B-stderr"),
        "C": (b"C-stdout", b"C-stderr"),
        "D": (b"D-stdout", b"D-stderr"),
        "E": (b"E-stdout", b"E-stderr"),
        "F": (b"F-stdout", b"F-stderr"),
        "G": (b"G-stdout", b"G-stderr"),
    }


def test_dag_graph(setup_dag):
    """Test Dependency Correctness."""
    dag = setup_dag
    assert dag.graph == {
        "A": set(),
        "B": set(),
        "C": {"A"},
        "D": {"A", "B"},
        "E": {"B"},
        "F": {"A", "D"},
        "G": {"A", "C", "E"}
    }


def test_dag_properties(setup_dag):
    """Test Dag Property Value Correctness."""
    dag = setup_dag
    assert set(dag.names) == {"A", "B", "C", "D", "E", "F", "G"}
    assert len(dag.names) == 7
    assert dag.sorted_names == ["A", "B", "C", "D", "E", "F", "G"]

    for startable in dag.startables:
        assert isinstance(startable, Node)

    assert isinstance(dag.sorter, TopologicalSorter)


def test_dag_results(setup_dag, setup_expected_results):
    """Test Consistency in Results."""
    dag = setup_dag
    expected_results = setup_expected_results
    results = dag.start()

    assert len(results) == len(expected_results)
    assert results == expected_results


# ======================================================================================================================


def test_dag_when_1_startable(setup_dag_kind, setup_nodes):
    dag_kind = setup_dag_kind
    node_dict = setup_nodes

    dag = dag_kind(f"Mock-{dag_kind.__name__}")
    dag.add(node_dict["A"])
    results = dag.start()

    assert results == {"A": (b"A-stdout", b"A-stderr")}


def test_dag_when_2_startables_with_dependency(setup_dag_kind, setup_nodes):
    dag_kind = setup_dag_kind
    node_dict = setup_nodes

    dag = dag_kind(f"Mock-{dag_kind.__name__}")
    dag.do(node_dict["A"]).then(node_dict["B"])  # A --> B
    results = dag.start()

    expected_results = {
        "A": (b"A-stdout", b"A-stderr"),
        "B": (b"B-stdout", b"B-stderr")
    }

    assert results == expected_results


def test_dag_when_2_startables_without_dependency(setup_dag_kind, setup_nodes):
    dag_kind = setup_dag_kind
    node_dict = setup_nodes

    dag = dag_kind(f"Mock-{dag_kind.__name__}")
    dag.add(node_dict["A"])
    dag.add(node_dict["B"])
    results = dag.start()

    expected_results = {
        "A": (b"A-stdout", b"A-stderr"),
        "B": (b"B-stdout", b"B-stderr")
    }

    assert results == expected_results


def test_dag_when_cycle_exist(setup_dag_kind, setup_nodes):
    dag_kind = setup_dag_kind
    node_dict = setup_nodes

    dag = dag_kind(f"Mock-{dag_kind.__name__}")
    dag.do(node_dict["A"]).then(node_dict["B"])
    dag.do(node_dict["B"]).then(node_dict["C"])
    dag.do(node_dict["C"]).then(node_dict["A"])
    # A -> B
    # B -> C
    # C -> A  // Cycle

    with pytest.raises(CycleError):
        results = dag.start()
