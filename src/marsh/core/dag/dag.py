import os
import shutil
import asyncio
from pathlib import Path
from typing import Sequence, Tuple
from collections import deque

from .node import Node, NodeStateEnum
from marsh.utils.list_utils import remove_duplicates


class Dag:
    arcs: Sequence[Tuple[Node, Node]] = []

    def __init__(self, arcs: Sequence[Tuple[Node, Node]] | None = None):
        self.arcs = arcs or []

    @property
    def sources(self) -> Sequence[Node]:
        return remove_duplicates([x for x, _ in self.arcs if all((y, x) not in self.arcs for y, _ in self.arcs if y != x)])

    @property
    def sinks(self) -> Sequence[Node]:
        return remove_duplicates(
            [y for _, y in self.arcs 
             if all((y, x) not in self.arcs 
                    for _, x in self.arcs if x != y)]
        )

    @property
    def nodes(self) -> Sequence[Node]:
        return remove_duplicates([x for x, _ in self.arcs] + [y for _, y in self.arcs])

    def _is_in_dag(self, node: Node) -> None:
        """Raises ValueError if the given node is not in the DAG's nodes."""
        if node not in self.nodes:
            raise ValueError("The given node does not belong to the DAG.")

    def add_dep_pair(self, source_node: Node, sink_node: Node) -> "Dag":
        """
        Adds a dependency pair to the DAG after checking for cycles using topological_sort.
        Raises ValueError if the new edge introduces a cycle.
        """
        if self.nodes:
            self._is_in_dag(source_node)
            self._is_in_dag(sink_node)

        new_dag = Dag(deps=[*self.arcs, (source_node, sink_node)])

        # Check if the new node pair forms a cycle
        self.topological_sort(new_dag)  # Raises RecursionError if there is a cycle

        return new_dag

    @staticmethod
    def topological_sort(dag: "Dag") -> Sequence[Node]:
        """
        Returns True if there is a cycle when adding a new pair of nodes.

        This method uses the Topological Sort with DFS.

        Returns:
            bool: True if adding a new pair of nodes would form a cycle; Otherwise False.
        """
        sorted_nodes = deque()
        visited = []
        temp_visited = []

        def visit(node: Node):
            nonlocal sorted_nodes, visited, temp_visited
            if node in visited:
                return
            if node in temp_visited:
                raise RecursionError(f"Cycle detected.")

            temp_visited.append(node)

            # Visit all neighbors (children in the DAG)
            for neighbor in (neighbor for src, neighbor in dag.arcs if src == node):
                visit(neighbor)

            temp_visited.remove(node)
            visited.append(node)
            sorted_nodes.appendleft(node)

        # Process all nodes in the DAG
        for dag_node in dag.nodes:
            if dag_node not in visited:
                visit(dag_node)

        return sorted_nodes

    def all_dependencies(self, node: Node, deps: Sequence[Node] | None = None) -> Sequence[Node]:
            # Direct and Non-Direct Dependencies of a node
            out_set = []
            for path in self.enumerate_paths():
                if node in path:
                    idx = path.index(node)
                    out_set += path[:idx]
            return out_set

    def direct_dependecies(self, node: Node) -> Sequence[Node]:
        # Returns a list of the direct dependency nodes of a given node.
        # Example: A -> B -> C, where B is a direct dependency of C and A is a direct dependency of B
        return [x for x, y in self.arcs if y == node]

    def neighbors(self, node: Node) -> Sequence[Node]:
        # Example: A -> B and A -> C, {B, C} are neighbors of A.
        self._is_in_dag(node)
        return [y for x, y in self.arcs if x == node]

    def enumerate_paths(self) -> Sequence[Sequence[Node]]:
        out_list: list[tuple[Node]] = []

        def dfs(node: Node, path: tuple[Node]):
            # Create a new path by adding the current node to the existing immutable path
            new_path = path + (node,)

            # If the node has no neighbors (it's a sink), add the path to the result
            if len(self.neighbors(node)) == 0:
                out_list.append(new_path)
            else:
                # Recurse to each neighbor (DFS)
                for neighbor in self.neighbors(node):
                    dfs(neighbor, new_path)  # Pass the new immutable path

        # Start DFS from all source nodes
        for source_node in self.sources:
            dfs(source_node, ())  # Start with an empty tuple for the path

        return out_list

    def level(self, node: Node, path: Sequence[Node]) -> int:
        self._is_in_dag(node)
        if node not in path:
            return -1
        return path.index(node)


class Conduit:
    def __init__(self, dag: Dag, temp_dir: str):        
        self._dag = dag
        self._temp_dir = temp_dir
    
    def _check_if_node_ready(self, node: Node) -> bool:
        return all(dep.state == NodeStateEnum.COMPLETE for dep in self._dag.direct_dependecies(node))

    def _check_if_all_nodes_complete(self) -> bool:
        return all(node.state == NodeStateEnum.COMPLETE for node in self._dag.nodes)

    def _get_idle_node(self) -> Sequence[Node]:
        return [node for node in self._dag.nodes if node.state == NodeStateEnum.IDLE]

    async def _run_node_async(self, node: Node, dependencies: list[str]) -> None:
        """Asynchronous wrapper to run a node."""
        # Set Node State to RUNNING
        node.set_state(NodeStateEnum.RUNNING)

        # Start the node's execution in a separate thread
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, node.start, dependencies)

    async def _execute_ready_nodes(self, running_tasks: set[asyncio.Task]) -> None:
        """Find READY nodes and execute them asynchronously."""
        for node in (idle_node for idle_node in self._dag.nodes if idle_node.state == NodeStateEnum.IDLE):
            # Check if all dependencies are COMPLETE
            if self._check_if_node_ready(node):
                node.set_state(NodeStateEnum.READY)
                dependencies = [dep.label for dep in self._dag.direct_dependecies(node)]

                # Schedule the node execution asynchronously
                task = asyncio.create_task(self._run_node_async(node, dependencies))
                running_tasks.add(task)

    async def _main_loop(self, delay=0.1) -> None:
        """Main loop to manage the DAG execution."""
        running_tasks = set()

        # Initialize Source Nodes in READY state and run them
        for src_node in self._dag.sources:
            src_node.set_state(NodeStateEnum.READY)
            task = asyncio.create_task(self._run_node_async(src_node, []))
            running_tasks.add(task)

        # Continuously check for READY nodes and execute them
        while not self._check_if_all_nodes_complete():
            await self._execute_ready_nodes(running_tasks)
            await asyncio.sleep(delay)  # Small delay to avoid busy waiting

        # Wait for all tasks to finish
        if running_tasks:
            await asyncio.gather(*running_tasks)

    def start(self) -> None:
        """Start the DAG execution."""
        # Delete the results temporary directory, if exists
        shutil.rmtree(self._temp_dir, ignore_errors=True)

        # Initialize the results temporary directory
        os.makedirs(self._temp_dir)

        try:
            asyncio.run(self._main_loop())
        finally:
            # Clean up the temporary directory
            shutil.rmtree(self._temp_dir, ignore_errors=True)
