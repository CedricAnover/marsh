from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from marsh.core.artifacts import Artifact, ArtifactRef
from marsh.core.identity import content_digest


class LocalArtifactStore:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.manifests = self.root / "manifests"
        self.tmp = self.root / "tmp"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.manifests.mkdir(parents=True, exist_ok=True)
        self.tmp.mkdir(parents=True, exist_ok=True)

    def path_for(self, ref: ArtifactRef) -> Path:
        digest = ref.digest.removeprefix("sha256:")
        if len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise ValueError("invalid artifact digest")
        return self.objects / digest[:2] / digest[2:]

    def manifest_path_for(self, ref: ArtifactRef) -> Path:
        return self.manifests / f"{ref.digest.removeprefix('sha256:')}.json"

    def put(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
    ) -> ArtifactRef:
        if not isinstance(data, bytes):
            raise TypeError("artifact data must be bytes")

        digest = content_digest(data)
        ref = Artifact(digest=digest, size=len(data), media_type=media_type)
        destination = self.path_for(ref)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            self.get(ref)
        else:
            fd, temp_name = tempfile.mkstemp(prefix="artifact-", dir=self.tmp)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, destination)
            finally:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass

        manifest = {
            "digest": digest,
            "size": len(data),
            "media_type": media_type,
        }
        manifest_path = self.manifest_path_for(ref)
        if manifest_path.exists():
            existing = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            if (
                existing.get("digest") != digest
                or existing.get("size") != len(data)
            ):
                raise ValueError(
                    "artifact manifest integrity verification failed"
                )
            if existing.get("media_type") != media_type:
                raise ValueError("artifact metadata conflict")
        else:
            fd, temp_name = tempfile.mkstemp(
                prefix="manifest-", dir=self.tmp, text=True
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(
                        manifest,
                        handle,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, manifest_path)
            finally:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass

        return Artifact(
            digest=digest,
            size=len(data),
            media_type=media_type,
            storage_ref=str(destination),
            manifest=manifest,
        )

    def get(self, ref: ArtifactRef) -> bytes:
        path = self.path_for(ref)
        if not path.is_file():
            raise FileNotFoundError(path)
        data = path.read_bytes()
        if len(data) != ref.size or content_digest(data) != ref.digest:
            raise ValueError("artifact integrity verification failed")
        return data

    def exists(self, ref: ArtifactRef) -> bool:
        return self.path_for(ref).is_file()

    def verify(self, ref: ArtifactRef) -> bool:
        self.get(ref)
        return True

    def delete(self, ref: ArtifactRef) -> None:
        self.path_for(ref).unlink(missing_ok=True)
        self.manifest_path_for(ref).unlink(missing_ok=True)

    def object_count(self) -> int:
        return sum(
            1 for path in self.objects.glob("*/*") if path.is_file()
        )
