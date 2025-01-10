import asyncio
import threading
import multiprocessing
from concurrent.futures import as_completed, Future, ThreadPoolExecutor, ProcessPoolExecutor
from graphlib import TopologicalSorter
from typing import Dict, Optional, Set, List, Tuple, Self, Any

from .startable import Startable


class Dag(Startable):
    def __init__(self, name):
        super().__init__(name)
        self._startables: Dict[str, Startable] = {}
        self._graph: Dict[str, Set[str]] = {}
        self._sorter: Optional[TopologicalSorter] = None
        self._last_startable: Optional[List[Startable]] = []

    @property
    def startables(self) -> List[Startable]:
        return list(self._startables.values())

    @property
    def names(self) -> List[str]:
        return list(self._startables.keys())

    @property
    def sorted_names(self) -> List[str]:
        sorter = self.sorter
        if sorter is None: return []
        return list(sorter.static_order())

    @property
    def sorter(self) -> Optional[TopologicalSorter]:
        return TopologicalSorter(graph=self._graph) if self._graph else None

    @property
    def graph(self) -> Dict[str, Set[str]]:
        return self._graph

    def reset(self) -> None:
        self._startables.clear()
        self._sorter = TopologicalSorter()
        self._graph.clear()
        self._last_startable = []

    def add(self, dependent: Startable, *dependencies: Startable) -> Self:
        """Adds a startable and its dependencies to the DAG."""
        # Update the Startable Dictionary
        self._startables[dependent.name] = dependent

        for dependency in dependencies:
            self._startables[dependency.name] = dependency

        # # Update the Graph Dictionary
        # dependency_set: set[str] = self._graph.get(dependent.name, set())
        # self._graph[dependent.name] = dependency_set | set([dependency.name for dependency in dependencies])
        self._graph.setdefault(dependent.name, set()).update([d.name for d in dependencies])

        return self

    def remove(self, startable: Startable) -> None:
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

    def do(self, *startables: Startable) -> Self:
        for startable in startables:
            self.add(startable)

        self._last_startable = startables
        return self

    def then(self, *dependents: Startable) -> Self:
        assert dependents, "Dependents cannot be empty."

        for dependent in dependents:
            self.add(dependent, *self._last_startable)

        self._last_startable = dependents  # Updated to avoid side effects
        return self

    def when(self, *dependencies: Startable) -> Self:
        assert dependencies, "Dependencies cannot be empty."

        for dependent in self._last_startable:
            self.add(dependent, *dependencies)

        return self

    def start(self) -> Dict[str, Tuple[bytes, bytes] | dict]:
        raise NotImplementedError("Add implementation to Dag.start")


class SyncDag(Dag):
    def start(self) -> Dict[str, Any]:
        results = {}
        for name in self.sorted_names:
            startable = self._startables[name]
            result = startable.start()
            results[startable.name] = result

        return results


class AsyncDag(Dag):
    def __init__(self, name: str, max_coroutines: int = 20, timeout: float = 600):
        super().__init__(name)
        self._max_coroutines = max_coroutines
        self._timeout = timeout

    async def _worker(self,
                      sorter: TopologicalSorter,
                      startable: Startable,
                      semaphore: asyncio.Semaphore,
                      lock: asyncio.Lock,
                      ) -> Dict[str, Any] | Tuple[bytes, bytes]:
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
        return asyncio.run(self._main_loop())


class ThreadPoolDag(Dag):
    def __init__(self, name: str, max_workers: int = 6):
        super().__init__(name)
        self._max_workers = max_workers

    def _worker(self,
                sorter: TopologicalSorter,
                startable: Startable,
                lock: threading.Lock,
                results: Dict[str, Any]
                ) -> None:

        result = startable.start()

        with lock:
            sorter.done(startable.name)
            results[startable.name] = result

    def start(self) -> Dict[str, Any]:
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
        super().__init__(name)
        self._max_workers = max_workers

    def _worker(self,
                sorter: TopologicalSorter,
                startable: Startable,
                results: Dict[str, Any],
                lock: threading.Lock,
                semaphore: threading.Semaphore
                ) -> None:
        with semaphore:
            result = startable.start()

            with lock:
                results[startable.name] = result

            with lock:
                sorter.done(startable.name)

    def start(self) -> Dict[str, Any]:
        sorter = self.sorter
        sorter.prepare()

        lock = threading.Lock()
        semaphore = threading.Semaphore(self._max_workers)  # Control the Number of Threads

        results: dict[str, Any] = {}
        workers: list[threading.Thread] = []

        # Start the Loop
        while sorter.is_active():
            ready_names = sorter.get_ready()
            with lock:
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
    def __init__(self, name: str, max_processes=4):
        super().__init__(name)
        self._max_processes = max_processes

    @staticmethod
    def _worker(ns, lock, startable_queue, done_queue) -> None:
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
        while not (stop_event.is_set() and done_queue.empty() and not sorter.is_active()):
            if not done_queue.empty():
                startable = done_queue.get()
                with lock:
                    sorter.done(startable.name)
                done_queue.task_done()

    def start(self) -> Dict[str, Any]:
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
    def __init__(self, name: str, max_processes: int = 4):
        super().__init__(name)
        self._max_processes = max_processes

    def start(self) -> Dict[str, Any]:
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
