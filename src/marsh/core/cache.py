"""Deterministic, opt-in result caching."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from marsh.core.domain import ProcessSpec, Result, Task
from marsh.core.serialization import _data


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
            "operation": _data(task.operation),
            "inputs": _to_data(task.inputs),
            "resources": _to_data(task.metadata.get("resources", {})),
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
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(encoded).hexdigest()
