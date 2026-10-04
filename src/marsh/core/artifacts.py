from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class Provenance:
    schema_version: int
    workflow_id: str
    workflow_version: str | None = None
    task_id: str | None = None
    execution_id: str | None = None
    attempt_id: str | None = None
    parent_execution_ids: tuple[str, ...] = ()
    operation_ref: Mapping[str, Any] | None = None
    provider_fingerprint: str | None = None
    machine_fingerprint: str | None = None
    policy_fingerprint: str | None = None
    input_artifact_refs: tuple[str, ...] = ()
    output_artifact_refs: tuple[str, ...] = ()
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("provenance schema_version must be positive")
        if not self.workflow_id:
            raise ValueError("provenance workflow_id must be non-empty")
        object.__setattr__(
            self, "parent_execution_ids", tuple(self.parent_execution_ids)
        )
        object.__setattr__(
            self, "input_artifact_refs", tuple(self.input_artifact_refs)
        )
        object.__setattr__(
            self, "output_artifact_refs", tuple(self.output_artifact_refs)
        )
        if self.operation_ref is not None:
            object.__setattr__(self, "operation_ref", dict(self.operation_ref))

    def to_dict(self) -> dict[str, Any]:
        values = {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "attempt_id": self.attempt_id,
            "parent_execution_ids": list(self.parent_execution_ids),
            "operation_ref": (
                dict(self.operation_ref) if self.operation_ref else None
            ),
            "provider_fingerprint": self.provider_fingerprint,
            "machine_fingerprint": self.machine_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "input_artifact_refs": list(self.input_artifact_refs),
            "output_artifact_refs": list(self.output_artifact_refs),
            "created_at": self.created_at,
        }
        return {
            key: value for key, value in values.items() if value is not None
        }


@dataclass(frozen=True)
class Artifact:
    digest: str
    size: int
    media_type: str = "application/octet-stream"
    storage_ref: str | None = None
    manifest: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _DIGEST.fullmatch(self.digest):
            raise ValueError(
                "artifact digest must be sha256:<64 hex characters>"
            )
        if self.size < 0:
            raise ValueError("artifact size cannot be negative")
        if not self.media_type:
            raise ValueError("artifact media_type must be non-empty")
        object.__setattr__(self, "manifest", dict(self.manifest))


ArtifactRef = Artifact


class ArtifactStore(Protocol):
    def put(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
    ) -> ArtifactRef:
        ...

    def get(self, ref: ArtifactRef) -> bytes:
        ...

    def exists(self, ref: ArtifactRef) -> bool:
        ...

    def verify(self, ref: ArtifactRef) -> bool:
        ...

    def delete(self, ref: ArtifactRef) -> None:
        ...
