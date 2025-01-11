import time
import random
from pprint import pprint

from marsh import Conveyor
from marsh.dag import Node, SyncDag, AsyncDag, ThreadPoolDag, ThreadDag, MultiprocessDag, ProcessPoolDag


def mock_cmd_runner(x_stdout, x_stderr, name, sleep_for=0.001):
    time.sleep(sleep_for)
    return f"{name}-stdout".encode(), x_stderr


if __name__ == "__main__":
    node_a = Node("A", Conveyor().add_cmd_runner(mock_cmd_runner, "A"))
    node_b = Node("B", Conveyor().add_cmd_runner(mock_cmd_runner, "B"))
    node_c = Node("C", Conveyor().add_cmd_runner(mock_cmd_runner, "C"))
    node_d = Node("D", Conveyor().add_cmd_runner(mock_cmd_runner, "D", sleep_for=3))  # Simulate Blocking
    node_e = Node("E", Conveyor().add_cmd_runner(mock_cmd_runner, "E"))
    node_f = Node("F", Conveyor().add_cmd_runner(mock_cmd_runner, "F"))
    node_g = Node("G", Conveyor().add_cmd_runner(mock_cmd_runner, "G", sleep_for=0.5))

    sync_dag_1 = SyncDag("SyncDag-1")
    sync_dag_1.do(node_a).then(node_b, node_c)

    sync_dag_2 = SyncDag("SyncDag-2")
    sync_dag_2.do(node_e).then(node_f)

    async_dag_1 = AsyncDag("AsyncDag-1", max_coroutines=30, timeout=4)
    async_dag_1.do(node_a).then(node_c, node_d, node_f, node_g)
    async_dag_1.do(node_b).then(node_d, node_e)
    async_dag_1.do(node_c).then(node_g)
    async_dag_1.do(node_d).then(node_f)
    async_dag_1.do(node_e).then(node_g)
    async_dag_1.do(node_f).then(sync_dag_2)
    # results = async_dag_1.start()
    # assert len(results) == 8

    thread_pool_dag_1 = ThreadPoolDag("ThreadPoolDag-1", max_workers=4)
    thread_pool_dag_1.do(node_a).then(node_c, node_d, node_f, node_g)
    thread_pool_dag_1.do(node_b).then(node_d, node_e)
    thread_pool_dag_1.do(node_c).then(node_g)
    thread_pool_dag_1.do(node_d).then(node_f)
    thread_pool_dag_1.do(node_e).then(node_g)
    # results = thread_pool_dag_1.start()
    # assert len(results) == 7

    thread_dag_1 = ThreadDag("ThreadDag-1", max_workers=6)
    thread_dag_1.do(node_a).then(node_c, node_d, node_f, node_g)
    thread_dag_1.do(node_b).then(node_d, node_e)
    thread_dag_1.do(node_c).then(node_g)
    thread_dag_1.do(node_d).then(node_f)
    thread_dag_1.do(node_e).then(node_g)
    # results = thread_dag_1.start()
    # assert len(results) == 7

    sync_dag_3 = SyncDag("SyncDag-3")
    sync_dag_3.do(sync_dag_1).then(sync_dag_2, thread_pool_dag_1)
    sync_dag_3.do(async_dag_1).when(sync_dag_2)
    # results = sync_dag_3.start()
    
    multiprocess_dag_1 = MultiprocessDag("MultiprocessDag-1", max_processes=4)
    multiprocess_dag_1.do(node_a).then(node_c, node_d, node_f, node_g)
    multiprocess_dag_1.do(node_b).then(node_d, node_e)
    multiprocess_dag_1.do(node_c).then(node_g)
    multiprocess_dag_1.do(node_d).then(node_f)
    multiprocess_dag_1.do(node_e).then(node_g)
    # results = multiprocess_dag_1.start()
    # assert len(results) == 7

    process_pool_dag_1 = ProcessPoolDag("ProcessPoolDag-1", max_processes=4)
    process_pool_dag_1.do(node_a).then(node_c, node_d, node_f, node_g)
    process_pool_dag_1.do(node_b).then(node_d, node_e)
    process_pool_dag_1.do(node_c).then(node_g)
    process_pool_dag_1.do(node_d).then(node_f)
    process_pool_dag_1.do(node_e).then(node_g)
    print(process_pool_dag_1.graph)
    results = process_pool_dag_1.start()
    assert len(results) == 7

    pprint(results, indent=4, width=60, depth=20)
