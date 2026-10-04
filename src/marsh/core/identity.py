from __future__ import annotations

import hashlib
import json
from typing import Any

from marsh.core.domain import Workflow
from marsh.core.serialization import workflow_to_json


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, Workflow):
        return workflow_to_json(value).encode("utf-8")
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"unsupported identity value: {type(value).__name__}"
        ) from exc
    return encoded.encode("utf-8")


def content_digest(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("content must be bytes")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def execution_id(
    workflow: Workflow,
    *,
    semantic_inputs: Any = None,
    policy: Any = None,
) -> str:
    payload: dict[str, Any] = {
        "schema": "marsh.execution/v1",
        "workflow": json.loads(workflow_to_json(workflow)),
    }
    if semantic_inputs is not None:
        payload["semantic_inputs"] = semantic_inputs
    if policy is not None:
        payload["policy"] = policy
    return content_digest(canonical_bytes(payload))
