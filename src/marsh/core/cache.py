"""Deterministic, opt-in result caching."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from marsh.core.domain import ProcessSpec, Result, Task


class Cache(Protocol):
    def get(self, key: str) -> Result | None:
        ...

    def put(self, key: str, result: Result) -> None:
        ...


@dataclass
class MemoryCache:
    _values: dict[str, Result]

    def __init__(self):
        self._values = {}

    def get(self, key: str) -> Result | None:
        return self._values.get(key)

    def put(self, key: str, result: Result) -> None:
        self._values[key] = result


@dataclass(frozen=True)
class CachePolicy:
    enabled: bool = False
    namespace: str = "marsh"

    def __post_init__(self) -> None:
        if not self.namespace.strip():
            raise ValueError("cache namespace must be non-empty")


def cache_key_for_task(
    task: Task,
    dependency_results: Mapping[str, Result],
    *,
    namespace: str = "marsh",
) -> str | None:
    if not isinstance(task.operation, ProcessSpec):
        return None

    try:
        payload: dict[str, Any] = {
            "namespace": namespace,
            "task_id": task.id,
            "operation": {
                "executable": task.operation.executable,
                "arguments": list(task.operation.arguments),
                "environment": dict(sorted(task.operation.environment.items())),
                "working_directory": task.operation.working_directory,
                "stdin": task.operation.stdin.hex()
                if task.operation.stdin is not None
                else None,
                "timeout": task.operation.timeout,
                "machine": task.operation.machine,
                "resources": dict(sorted(task.operation.resources.items())),
                "metadata": task.operation.metadata,
            },
            "inputs": task.inputs,
            "resources": task.metadata.get("resources", {}),
            "dependencies": {
                name: {
                    "stdout": result.stdout.hex(),
                    "stderr": result.stderr.hex(),
                    "exit_code": result.exit_code,
                    "status": result.status.value,
                    "error": result.error,
                }
                for name, result in sorted(dependency_results.items())
            },
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(encoded).hexdigest()
