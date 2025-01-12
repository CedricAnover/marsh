import asyncio
import threading
import multiprocessing
from concurrent.futures import as_completed, Future, ThreadPoolExecutor, ProcessPoolExecutor
from graphlib import TopologicalSorter
from typing import Dict, Optional, Set, List, Tuple, Any

from .startable import Startable


class Dag(Startable):
    """
    Base class representing a Directed Acyclic Graph (DAG) of Startable objects.

    The `Dag` class manages a collection of `Startable` objects and defines their dependencies. Subclasses
    of `Dag` implement different strategies for executing the startable objects (e.g., synchronously, asynchronously,
    using threads or processes).

    Attributes:
        _startables (dict): A dictionary mapping startable names to `Startable` objects.
        _graph (dict): A dictionary representing the dependency graph of startables.
        _sorter (Optional[TopologicalSorter]): A topological sorter used to order the startables based on dependencies.
        _last_startable (Optional[List[Startable]]): The list of the most recently added startables.

    Methods:
        add(dependent, *dependencies): Adds a dependent `Startable` and its dependencies to the DAG.
        remove(startable): Removes a `Startable` from the DAG.
        do(*startables): Adds the specified startables to the DAG and marks them as the last startables.
        then(*dependents): Specifies the dependents of the last startables, adding them to the DAG.
        when(*dependencies): Specifies the dependencies for the last startables.
        start(): Starts the DAG execution (method to be overriden by subclasses).
    """

    def __init__(self, name):
        """
        Initializes a DAG with the specified name.

        Args:
            name (str): The name of the DAG.
        """
        super().__init__(name)
        self._startables: Dict[str, Startable] = {}
        self._graph: Dict[str, Set[str]] = {}
        self._sorter: Optional[TopologicalSorter] = None
        self._last_startable: Optional[List[Startable]] = []

    @property
    def startables(self) -> List[Startable]:
        """
        Returns a list of all `Startable` objects in the DAG.

        Returns:
            List[Startable]: A list of all `Startable` objects managed by the DAG.
        """
        return list(self._startables.values())

    @property
    def names(self) -> List[str]:
        """
        Returns a list of the names of all `Startable` objects in the DAG.

        Returns:
            List[str]: A list of names of all `Startable` objects.
        """
        return list(self._startables.keys())

    @property
    def sorted_names(self) -> List[str]:
        """
        Returns a list of startable names in topologically sorted order.

        This property depends on the dependency graph of the startables.

        Returns:
            List[str]: A list of startable names sorted by their dependencies.
        """
        sorter = self.sorter
        if sorter is None: return []
        return list(sorter.static_order())

    @property
    def sorter(self) -> Optional[TopologicalSorter]:
        """
        Returns a TopologicalSorter instance based on the DAG's dependency graph.

        This property computes a `TopologicalSorter` when the graph is not empty.

        Returns:
            Optional[TopologicalSorter]: The topological sorter instance or `None` if the graph is empty.
        """
        return TopologicalSorter(graph=self._graph) if self._graph else None

    @property
    def graph(self) -> Dict[str, Set[str]]:
        """
        Returns the dependency graph of startables in the DAG.

        The graph is represented as a dictionary, where each key is the dependent startable name, and each value
        is a set of names of other startable dependencies of the dependent startable.

        Returns:
            Dict[str, Set[str]]: The dependency graph of startables.
        """
        return self._graph

    def reset(self) -> None:
        """
        Resets the DAG, clearing all startables and dependencies.

        This method clears the `_startables`, `_graph`, and `_last_startable` attributes.
        It also resets the topological sorter.
        """
        self._startables.clear()
        self._sorter = TopologicalSorter()
        self._graph.clear()
        self._last_startable = []

    def add(self, dependent: Startable, *dependencies: Startable) -> "Dag":
        """
        Adds a dependent `Startable` and its dependencies to the DAG.

        Args:
            dependent (Startable): The `Startable` to be added as a dependent in the DAG.
            *dependencies (Startable): The `Startable` objects that the dependent depends on.

        Returns:
            Dag: The updated `Dag` instance with the newly added dependent and its dependencies.
        """
        # Update the Startable Dictionary
        self._startables[dependent.name] = dependent

        for dependency in dependencies:
            self._startables[dependency.name] = dependency

            # Make sure that if the dependency is not yet registered to the graph,
            # then add them with with default empty set for their own dependencies.
            self._graph[dependency.name] = self._graph.get(dependency.name, set())

        # Update the Graph Dictionary
        # dependency_set: set[str] = self._graph.get(dependent.name, set())
        # self._graph[dependent.name] = dependency_set | set([dependency.name for dependency in dependencies])
        self._graph.setdefault(dependent.name, set()).update([d.name for d in dependencies])

        return self

    def remove(self, startable: Startable) -> None:
        """
        Removes a `Startable` from the DAG.

        Args:
            startable (Startable): The `Startable` to be removed from the DAG.
        """
        try:
            del self._startables[startable.name]
        except KeyError:
            pass

        # Remove the startable from Graph Dictionary
        try:
            del self._graph[startable.name]
        except KeyError:
            pass

        # Remove the startable from some dependency set of other startable in graph dictionary
        for name, dependency_set in self._graph.items():
            if startable.name in dependency_set:
                self._graph[name].remove(startable.name)

    def do(self, *startables: Startable) -> "Dag":
        """
        Adds the specified `Startable` objects to the DAG and marks them as the last added startables.

        Args:
            *startables (Startable): The `Startable` objects to be added to the DAG.

        Returns:
            Dag: The updated `Dag` instance with the newly added startables.
        """
        for startable in startables:
            self.add(startable)

        self._last_startable = startables
        return self

    def then(self, *dependents: Startable) -> "Dag":
        """
        Specifies the dependents of the last added startables, adding them to the DAG.

        Args:
            *dependents (Startable): The `Startable` objects that depend on the last added startables.

        Returns:
            Dag: The updated `Dag` instance with the newly added dependents.
        """
        assert dependents, "Dependents cannot be empty."

        for dependent in dependents:
            self.add(dependent, *self._last_startable)

        self._last_startable = dependents  # Updated to avoid side effects
        return self

    def when(self, *dependencies: Startable) -> "Dag":
        """
        Specifies the dependencies for the last added startables.

        Args:
            *dependencies (Startable): The `Startable` objects that the last added startables depend on.

        Returns:
            Dag: The updated `Dag` instance with the newly added dependencies.
        """
        assert dependencies, "Dependencies cannot be empty."

        for dependent in self._last_startable:
            self.add(dependent, *dependencies)

        return self

    def start(self) -> Dict[str, Tuple[bytes, bytes] | dict]:
        """
        Starts the DAG execution.

        This method should be implemented by subclasses to define how the startables are executed.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("Add implementation to Dag.start")


class SyncDag(Dag):
    """
    A synchronous implementation of the `Dag` class.

    The `SyncDag` class executes all startable objects in the DAG sequentially, ensuring that each startable
    is executed only after its dependencies have been completed.

    Methods:
        start(): Executes the startables sequentially and returns the results as a dictionary.
    """

    def start(self) -> Dict[str, Any]:
        """
       Starts the DAG execution synchronously.

       Executes each startable in topologically sorted order and returns the results in a dictionary.

       Returns:
           Dict[str, Any]: A dictionary mapping startable names to their results.
       """
        results = {}
        for name in self.sorted_names:
            startable = self._startables[name]
            result = startable.start()
            results[startable.name] = result

        return results


class AsyncDag(Dag):
    """
    An asynchronous implementation of the `Dag` class using asyncio.

    The `AsyncDag` class executes startable objects concurrently, using asyncio to manage coroutines and tasks
    for parallel execution, while respecting the dependencies defined by the DAG structure.

    Attributes:
        _max_coroutines (int): The maximum number of concurrent coroutines allowed.
        _timeout (float): The maximum time (in seconds) to wait for each startable.

    Methods:
        _worker(sorter, startable, semaphore, lock): Worker function that runs the startable asynchronously.
        _main_loop(): Main loop that manages execution and ensures tasks are completed in dependency order.
        start(): Starts the DAG execution asynchronously and returns the results as a dictionary.
    """

    def __init__(self, name: str, max_coroutines: int = 20, timeout: float = 600):
        """
        Initializes a AsyncDag with the specified name, maximum number of coroutines, and timeout.

        Args:
            name (str): The name of the AsyncDag.
            max_coroutines (int, optional): The maximum number of concurrent coroutines. Defaults to 20.
            timeout (float, optional): The time limit (seconds) for running a startable. Defaults to 600.
        """
        super().__init__(name)
        self._max_coroutines = max_coroutines
        self._timeout = timeout

    async def _worker(self,
                      sorter: TopologicalSorter,
                      startable: Startable,
                      semaphore: asyncio.Semaphore,
                      lock: asyncio.Lock,
                      ) -> Dict[str, Any] | Tuple[bytes, bytes]:
        """
        Worker function to execute a startable asynchronously with a semaphore.

        Args:
            sorter (TopologicalSorter): The sorter to update as tasks are completed.
            startable (Startable): The startable to execute.
            semaphore (asyncio.Semaphore): Limits the number of concurrent coroutines.
            lock (asyncio.Lock): Ensures thread safety when updating the sorter.

        Returns:
            Tuple[str, Any]: A tuple containing the startable name and its result.
        """

        async with semaphore:
            try:
                result = await asyncio.wait_for(asyncio.to_thread(startable.start), self._timeout)
            except TimeoutError:
                raise TimeoutError(f"{startable.name} exceeded {self._timeout} seconds.")

            # Ensure only one task updates the TopologicalSorter at a time
            async with lock:
                sorter.done(startable.name)

            return startable.name, result

    async def _main_loop(self) -> Dict[str, Any]:
        """
        Main loop to execute startables concurrently in topological order.

        Returns:
            Dict[str, Any]: A dictionary mapping startable names to their results.
        """
        sorter = self.sorter
        sorter.prepare()

        semaphore = asyncio.Semaphore(self._max_coroutines)  # Limit concurrent coroutines
        lock = asyncio.Lock()
        tasks = []
        results = []

        while sorter.is_active():
            ready_names = sorter.get_ready()
            for name in ready_names:
                startable = self._startables[name]
                task = asyncio.create_task(self._worker(sorter, startable, semaphore, lock))
                tasks.append(task)

            # Wait for at least one task to finish before continuing
            if tasks:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                tasks = list(pending)  # Keep only pending tasks for the next iteration

                # Collect results from completed tasks
                for completed_task in done:
                    result = await completed_task
                    results.append(result)

        # Ensure any remaining tasks are awaited and results collected
        if tasks:
            for task in tasks:
                result = await task
                results.append(result)

        return {name: result for name, result in results}

    def start(self) -> Dict[str, Any]:
        """
        Starts the asynchronous DAG execution.

        Returns:
            Dict[str, Any]: A dictionary mapping startable names to their results.
        """
        return asyncio.run(self._main_loop())


class ThreadPoolDag(Dag):
    """
    A `Dag` implementation using a thread pool.

    The `ThreadPoolDag` class executes startables concurrently using a thread pool, limiting the number of threads
    running concurrently to the specified maximum.

    Attributes:
        _max_workers (int): The maximum number of workers in the thread pool.

    Methods:
        _worker(sorter, startable, lock, results): Worker function to execute a startable in a thread.
        start(): Starts the DAG execution using the thread pool and returns the results as a dictionary.
    """

    def __init__(self, name: str, max_workers: int = 6):
        """
        Initializes the thread pool DAG with the given name and maximum number of worker threads.

        Args:
            name (str): The name of the DAG.
            max_workers (int, optional): The maximum number of worker threads. Defaults to 6.
        """
        super().__init__(name)
        self._max_workers = max_workers

    def _worker(self,
                sorter: TopologicalSorter,
                startable: Startable,
                lock: threading.Lock,
                results: Dict[str, Any]
                ) -> None:
        """
        Worker function to execute a startable in a thread.

        Args:
            sorter (TopologicalSorter): The sorter to update as tasks are completed.
            startable (Startable): The startable to execute.
            lock (threading.Lock): Ensures thread safety when updating the sorter.
            results (dict): A dictionary to store the results of executed startables.
        """

        result = startable.start()

        with lock:
            sorter.done(startable.name)
            results[startable.name] = result

    def start(self) -> Dict[str, Any]:
        """
        Starts the DAG execution using a thread pool.

        Returns:
            Dict[str, Any]: A dictionary mapping startable names to their results.
        """
        sorter = self.sorter
        sorter.prepare()

        lock = threading.Lock()
        results = {}

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures: list[Future] = []
            while sorter.is_active():
                ready_names = []
                with lock:
                    ready_names = sorter.get_ready()

                for name in ready_names:
                    startable = self._startables[name]
                    future = executor.submit(self._worker, sorter, startable, lock, results)
                    futures.append(future)

            for future in as_completed(futures):
                future.result()

        return results


class ThreadDag(Dag):
    def __init__(self, name: str, max_workers: int = 6):
        """
        Initializes the threaded DAG with the given name and maximum number of threads.

        Args:
            name (str): The name of the DAG.
            max_workers (int, optional): The maximum number of threads to run concurrently. Defaults to 6.
        """
        super().__init__(name)
        self._max_workers = max_workers

    def _worker(self,
                sorter: TopologicalSorter,
                startable: Startable,
                results: Dict[str, Any],
                lock: threading.Lock,
                semaphore: threading.Semaphore
                ) -> None:
        """
        Worker method to execute a task in a thread and update results.

        This method runs each task in a separate thread and updates the results and topological sorter.

        Args:
            sorter (TopologicalSorter): The topological sorter for the DAG.
            startable (Startable): The task to be executed.
            results (Dict[str, Any]): A dictionary to store task results.
            lock (threading.Lock): Lock to ensure thread-safe updates.
            semaphore (threading.Semaphore): Semaphore to limit the number of concurrent threads.
        """
        with semaphore:
            result = startable.start()

            with lock:
                results[startable.name] = result

            with lock:
                sorter.done(startable.name)

    def start(self) -> Dict[str, Any]:
        """
        Starts the execution of tasks in the DAG using threads.

        This method manages the execution of tasks using threads. It controls the maximum number of concurrent threads
        using a semaphore and collects results in a shared dictionary.

        Returns:
            Dict[str, Any]: A dictionary mapping task names to their results.
        """
        sorter = self.sorter
        sorter.prepare()

        lock = threading.Lock()
        semaphore = threading.Semaphore(self._max_workers)  # Control the Number of Threads

        results: dict[str, Any] = {}
        workers: list[threading.Thread] = []

        # Start the Loop
        while sorter.is_active():
            with lock:
                ready_names = sorter.get_ready()

            if ready_names:
                for name in ready_names:
                    # Dispatch a worker only if there's room in the semaphore
                    startable = self._startables[name]
                    thread = threading.Thread(
                        target=self._worker,
                        args=(sorter, startable, results, lock, semaphore),
                        daemon=True
                    )
                    thread.start()
                    workers.append(thread)

        # Wait for all threads to finish
        for thread in workers:
            thread.join()

        return results


class MultiprocessDag(Dag):
    """
    A Directed Acyclic Graph (DAG) that executes tasks concurrently using multiple worker processes.

    This class utilizes multiple processes to execute tasks in parallel, allowing for parallel computation across
    multiple CPU cores. Each task is processed by one of the available worker processes, while a marker thread
    tracks completed tasks and updates the DAG sorter to ensure task dependencies are respected. Tasks are
    submitted to a queue, executed, and results are stored in a shared namespace.

    Attributes:
        _max_processes (int): The maximum number of worker processes to use for concurrent execution. Default is 4.
    """

    def __init__(self, name: str, max_processes=4):
        """
        Initializes the multiprocess DAG with the given name and maximum number of worker processes.

        This class executes tasks concurrently using multiple processes, allowing parallel execution across different
        CPUs.

        Args:
            name (str): The name of the DAG.
            max_processes (int, optional): The maximum number of worker processes. Defaults to 4.
        """
        super().__init__(name)
        self._max_processes = max_processes

    @staticmethod
    def _worker(ns, lock, startable_queue, done_queue) -> None:
        """
        Worker method that processes tasks from the startable_queue and stores results in the shared namespace.

        Each worker takes tasks from the queue, processes them, and stores the result in a thread-safe dictionary.
        Once the task is completed, it is put into the done_queue to be marked as done for sorter.

        Args:
            ns (multiprocessing.Namespace): Shared namespace to store task results.
            lock (multiprocessing.Lock): A lock to synchronize access to the shared results.
            startable_queue (multiprocessing.Queue): Queue of startable tasks to be processed.
            done_queue (multiprocessing.Queue): Queue to track completed tasks.
        """
        while True:
            if not startable_queue.empty():
                startable = startable_queue.get()
                result = startable.start()

                with lock:
                    ns.results[startable.name] = result

                done_queue.put(startable)
                startable_queue.task_done()

    @staticmethod
    def _marker(sorter, lock, done_queue, stop_event) -> None:
        """
        Marker thread that tracks task completion and updates the sorter.

        The marker thread continually monitors the done_queue for completed tasks and updates the DAG sorter
        to mark tasks as done, ensuring the DAG is correctly processed.

        Args:
            sorter (TopologicalSorter): The sorter managing task dependencies.
            lock (multiprocessing.Lock): A lock to synchronize access to the sorter.
            done_queue (multiprocessing.Queue): Queue tracking tasks that have been completed.
            stop_event (multiprocessing.Event): Event to signal when the process should stop.
        """
        while not (stop_event.is_set() and done_queue.empty() and not sorter.is_active()):
            if not done_queue.empty():
                startable = done_queue.get()
                with lock:
                    sorter.done(startable.name)
                done_queue.task_done()

    def start(self) -> Dict[str, Any]:
        """
        Starts the execution of tasks in the DAG using multiple processes and a marker thread.

        The method prepares the DAG, starts worker processes to handle tasks in parallel, and uses a marker thread
        to track task completion. It ensures that all tasks are processed and results are collected.

        Args:
            name (str): The name of the DAG.

        Returns:
            Dict[str, Any]: A dictionary mapping task names to their results.
        """
        sorter = self.sorter
        sorter.prepare()

        with multiprocessing.Manager() as manager:
            # Use Namespace to share results
            ns = manager.Namespace()
            ns.results = manager.dict()  # Dictionary of Results

            # Mutex
            lock = manager.Lock()

            # Queues
            startable_queue = manager.Queue()
            done_queue = manager.Queue()

            # Events
            stop_event = manager.Event()

            # Start the Worker Processes
            workers: list[multiprocessing.Process] = []
            for _ in range(self._max_processes):
                process = multiprocessing.Process(
                    target=self._worker,
                    args=(ns, lock, startable_queue, done_queue),
                    daemon=True
                )
                process.start()
                workers.append(process)

            # Start the Marker Thread
            marker_thread = threading.Thread(
                target=self._marker,
                args=(sorter, lock, done_queue, stop_event),
                daemon=True
            )
            marker_thread.start()

            # Loop until all startables are processed and completed
            while sorter.is_active():
                with lock:
                    ready_names = sorter.get_ready()

                if ready_names:
                    for name in ready_names:
                        startable = self._startables[name]
                        startable_queue.put(startable)

            # Wait until all startables are processed
            startable_queue.join()

            # Wait until all startables are marked
            done_queue.join()

            # Set the Stop Event to signal the Processes and Thread
            stop_event.set()

            # Wait until marker is done
            marker_thread.join()

            # Terminate all worker processes
            for process in workers:
                process.terminate()

            return dict(ns.results)


class ProcessPoolDag(Dag):
    """
    A Directed Acyclic Graph (DAG) that executes tasks concurrently using a process pool.

    This class uses a `ProcessPoolExecutor` to execute tasks concurrently in a pool of worker processes. Tasks
    are submitted to the pool and executed in parallel. The results are gathered as they complete, and the task
    dependencies are handled by the DAG sorter to ensure tasks execute in the correct order.

    Attributes:
        _max_processes (int): The maximum number of processes to use in the pool for concurrent execution. Default is 4.
    """

    def __init__(self, name: str, max_processes: int = 4):
        """
        Initializes the process pool DAG with the given name and maximum number of worker processes in the pool.

        This class uses a process pool to execute tasks concurrently. Each task is submitted to the pool, and the results
        are tracked as they are completed.

        Args:
            name (str): The name of the DAG.
            max_processes (int, optional): The maximum number of processes to run concurrently in the process pool.
                Defaults to 4.
        """
        super().__init__(name)
        self._max_processes = max_processes

    def start(self) -> Dict[str, Any]:
        """
        Starts the execution of tasks in the DAG using a process pool.

        The method submits tasks to the process pool, waits for their completion, and collects results. It ensures that
        tasks are executed concurrently and the results are properly handled and sorted.

        Args:
            name (str): The name of the DAG.

        Returns:
            Dict[str, Any]: A dictionary mapping task names to their results.
        """
        sorter = self.sorter
        sorter.prepare()

        results = {}
        with ProcessPoolExecutor(max_workers=self._max_processes) as pool:
            futures: dict[Future, Startable] = {}

            while sorter.is_active():
                ready_names = sorter.get_ready()
                for name in ready_names:
                    startable = self._startables[name]
                    futures[pool.submit(startable.start)] = startable

                # Check completed futures without blocking others
                completed_futures = [f for f in futures if f.done()]  # Polling
                for future in completed_futures:
                    startable = futures[future]
                    result = future.result()
                    results[startable.name] = result
                    sorter.done(startable.name)
                    del futures[future]

        return results
