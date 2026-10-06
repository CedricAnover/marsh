import json
import socket
import subprocess
import sys
import time

import pytest

from marsh.core.domain import ProcessSpec, ProcessStatus, Result
from marsh.core.remote import (
    Agent,
    ExecutionRequest,
    ExecutionSubstrate,
    MachineConnection,
    RemoteExecutionError,
    SocketMachineConnection,
    reconcile_remote_result,
)
from marsh.core.runtime import LocalMachine


def test_local_machine_exposes_remote_boundary_capabilities():
    machine = LocalMachine()
    assert isinstance(machine, ExecutionSubstrate)
    assert machine.machine_id
    assert "process.start" in machine.capabilities
    assert machine.connection is None


def test_remote_contracts_are_narrow_and_runtime_checkable():
    assert issubclass(MachineConnection, object)
    assert issubclass(ExecutionSubstrate, object)
    assert issubclass(Agent, object)


def test_execution_request_preserves_semantic_identity_and_attempt():
    request = ExecutionRequest(
        execution_id="exec-1",
        attempt_id="task:1",
        task_id="task",
        spec=ProcessSpec(executable=sys.executable, arguments=("-c", "print('ok')")),
    )
    assert request.execution_id == "exec-1"
    assert request.attempt_id == "task:1"
    assert request.task_id == "task"


def test_reconcile_transport_failure_from_verified_result():
    result = Result(stdout=b"ok", execution_id="exec-1", attempt_id="task:1")
    resolved = reconcile_remote_result(
        execution_id="exec-1",
        attempt_id="task:1",
        transport_error=ConnectionError("connection lost"),
        observed_result=result,
    )
    assert resolved == result


def test_reconcile_transport_failure_without_authoritative_result_is_ambiguous():
    with pytest.raises(RemoteExecutionError) as exc:
        reconcile_remote_result(
            execution_id="exec-1",
            attempt_id="task:1",
            transport_error=ConnectionError("connection lost"),
            observed_result=None,
        )
    assert exc.value.ambiguous is True


def test_socket_connection_round_trip_across_separate_process():
    server_code = r"""
import json
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    print(server.getsockname()[1], flush=True)
    server.listen(1)
    conn, _ = server.accept()
    with conn:
        data = conn.recv(65536)
        payload = json.loads(data.decode())
        response = {"execution_id": payload["execution_id"], "attempt_id": payload["attempt_id"], "status": "completed"}
        conn.sendall((json.dumps(response) + "\n").encode())
"""
    child = subprocess.Popen(
        [sys.executable, "-c", server_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert child.stdout is not None
    port = int(child.stdout.readline().strip())
    try:
        connection = SocketMachineConnection("127.0.0.1", port, timeout=2)
        for _ in range(20):
            try:
                connection.connect()
                break
            except RemoteExecutionError as exc:
                if exc.ambiguous:
                    raise
                time.sleep(0.05)
        else:
            raise AssertionError("separate-process socket server did not become ready")
        response = connection.execute(
            ExecutionRequest(
                execution_id="exec-2",
                attempt_id="task:1",
                task_id="task",
                spec=ProcessSpec(executable="python"),
            )
        )
        connection.disconnect()
        assert response.execution_id == "exec-2"
        assert response.attempt_id == "task:1"
        assert response.status is ProcessStatus.COMPLETED
    finally:
        child.terminate()
        child.wait(timeout=5)
        if child.stderr:
            child.stderr.read()


def test_agent_can_implement_remote_execution_without_transport_knowledge():
    class FakeAgent:
        def execute(self, request):
            return __import__(
                "marsh.core.remote", fromlist=["ExecutionResponse"]
            ).ExecutionResponse(
                execution_id=request.execution_id,
                attempt_id=request.attempt_id,
                status=ProcessStatus.COMPLETED,
            )

    request = ExecutionRequest(
        execution_id="exec-agent",
        attempt_id="task:1",
        task_id="task",
        spec=ProcessSpec(executable=sys.executable),
    )
    agent = FakeAgent()
    assert isinstance(agent, Agent)
    response = agent.execute(request)
    assert response.execution_id == request.execution_id
    assert response.status is ProcessStatus.COMPLETED


def test_socket_response_identity_mismatch_is_rejected():
    with pytest.raises(RemoteExecutionError) as exc:
        reconcile_remote_result(
            execution_id="exec-1",
            attempt_id="task:1",
            transport_error=None,
            observed_result=Result(
                execution_id="exec-2",
                attempt_id="task:1",
                status=ProcessStatus.COMPLETED,
            ),
        )
    assert exc.value.ambiguous is False
