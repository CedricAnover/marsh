"""Transport-neutral remote execution contracts and reconciliation helpers.

The module defines the semantic boundary for remote execution without selecting a
production transport. Concrete connections adapt sockets, SSH, RPC, or another
mechanism to these contracts.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable

from marsh.core.domain import ProcessSpec, ProcessStatus, Result


class RemoteExecutionError(RuntimeError):
    """A remote boundary error whose outcome may be ambiguous."""

    def __init__(self, message: str, *, ambiguous: bool = True) -> None:
        super().__init__(message)
        self.ambiguous = ambiguous


@dataclass(frozen=True)
class ExecutionRequest:
    """Provider-independent request crossing a machine boundary."""

    execution_id: str
    attempt_id: str
    task_id: str
    spec: ProcessSpec

    def __post_init__(self) -> None:
        for name, value in (
            ("execution_id", self.execution_id),
            ("attempt_id", self.attempt_id),
            ("task_id", self.task_id),
        ):
            if not value or not value.strip():
                raise ValueError(f"{name} must be non-empty")


@dataclass(frozen=True)
class ExecutionResponse:
    """Observed response from a remote execution boundary."""

    execution_id: str
    attempt_id: str
    status: ProcessStatus
    result: Result | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.execution_id or not self.execution_id.strip():
            raise ValueError("execution_id must be non-empty")
        if not self.attempt_id or not self.attempt_id.strip():
            raise ValueError("attempt_id must be non-empty")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_wire(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "attempt_id": self.attempt_id,
            "status": self.status.value,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "ExecutionResponse":
        try:
            status = ProcessStatus(str(payload["status"]))
            return cls(
                execution_id=str(payload["execution_id"]),
                attempt_id=str(payload["attempt_id"]),
                status=status,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise RemoteExecutionError(
                "invalid remote execution response", ambiguous=False
            ) from exc


@runtime_checkable
class MachineConnection(Protocol):
    """Transport/session boundary; it does not own workflow semantics."""

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def execute(self, request: ExecutionRequest) -> ExecutionResponse: ...


@runtime_checkable
class Agent(Protocol):
    """Optional machine-side execution endpoint."""

    def execute(self, request: ExecutionRequest) -> ExecutionResponse: ...


@runtime_checkable
class ExecutionSubstrate(Protocol):
    """Execution environment that can materialize a Marsh process."""

    @property
    def machine_id(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[str]: ...

    @property
    def connection(self) -> MachineConnection | None: ...


def reconcile_remote_result(
    *,
    execution_id: str,
    attempt_id: str,
    transport_error: Exception | None,
    observed_result: Result | None,
) -> Result:
    """Resolve a transport interruption only when authoritative evidence exists."""

    if observed_result is not None:
        if (
            observed_result.execution_id != execution_id
            or observed_result.attempt_id != attempt_id
        ):
            raise RemoteExecutionError(
                "observed result identity does not match request",
                ambiguous=False,
            )
        return observed_result

    if transport_error is None:
        raise RemoteExecutionError(
            "remote execution produced no result or transport error",
            ambiguous=True,
        )

    raise RemoteExecutionError(
        f"remote execution outcome is ambiguous: {transport_error}",
        ambiguous=True,
    )


class SocketMachineConnection:
    """Small stdlib TCP adapter used to prove the semantic boundary.

    This is a conformance/reference adapter, not a production transport
    commitment. It exchanges one JSON request/response per execution.
    """

    def __init__(self, host: str, port: int, *, timeout: float = 10.0) -> None:
        if not host.strip():
            raise ValueError("host must be non-empty")
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None

    def connect(self) -> None:
        if self._socket is not None:
            return
        try:
            self._socket = socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            )
        except OSError as exc:
            raise RemoteExecutionError(
                f"unable to connect to remote execution endpoint: {exc}",
                ambiguous=False,
            ) from exc

    def disconnect(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        if self._socket is None:
            raise RemoteExecutionError(
                "machine connection is not connected", ambiguous=False
            )
        payload = {
            "execution_id": request.execution_id,
            "attempt_id": request.attempt_id,
            "task_id": request.task_id,
            "spec": {
                "executable": request.spec.executable,
                "arguments": list(request.spec.arguments),
                "environment": dict(request.spec.environment),
                "working_directory": request.spec.working_directory,
                "timeout": request.spec.timeout,
            },
        }
        try:
            self._socket.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            data = b""
            while not data.endswith(b"\n"):
                chunk = self._socket.recv(65536)
                if not chunk:
                    raise ConnectionError("remote endpoint closed the connection")
                data += chunk
            return ExecutionResponse.from_wire(json.loads(data.decode("utf-8")))
        except RemoteExecutionError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteExecutionError(
                f"remote execution transport failed: {exc}", ambiguous=True
            ) from exc
        finally:
            self.disconnect()


__all__ = [
    "Agent",
    "ExecutionRequest",
    "ExecutionResponse",
    "ExecutionSubstrate",
    "MachineConnection",
    "RemoteExecutionError",
    "SocketMachineConnection",
    "reconcile_remote_result",
]
