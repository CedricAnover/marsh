from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from marsh.core.artifacts import Artifact, ArtifactRef
from marsh.core.identity import content_digest

_READ_RETRIES = 8
_READ_RETRY_DELAY_SECONDS = 0.01


def _read_text_with_retry(path: Path) -> str:
    """Read a small metadata file across transient Windows replace locks."""
    for attempt in range(_READ_RETRIES):
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if attempt == _READ_RETRIES - 1:
                raise
            time.sleep(_READ_RETRY_DELAY_SECONDS * (attempt + 1))
    raise AssertionError("unreachable")


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
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("invalid artifact digest")
        return self.objects / digest[:2] / digest[2:]

    def manifest_path_for(self, ref: ArtifactRef) -> Path:
        return self.manifests / f"{ref.digest.removeprefix('sha256:')}.json"

    def _get_with_retry(self, ref: ArtifactRef) -> bytes:
        """Read an artifact across transient Windows file-sharing locks."""
        for attempt in range(_READ_RETRIES):
            try:
                return self.get(ref)
            except PermissionError:
                if attempt == _READ_RETRIES - 1:
                    raise
                time.sleep(_READ_RETRY_DELAY_SECONDS * (attempt + 1))
        raise AssertionError("unreachable")

    def _verify_manifest(self, ref: ArtifactRef) -> None:
        """Verify the persisted manifest against the artifact reference."""
        manifest_path = self.manifest_path_for(ref)
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        manifest = json.loads(_read_text_with_retry(manifest_path))
        if manifest.get("digest") != ref.digest or (manifest.get("size") != ref.size):
            raise ValueError("artifact manifest integrity verification failed")
        if manifest.get("media_type") != ref.media_type:
            raise ValueError("artifact metadata conflict")

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
            self._get_with_retry(ref)
        else:
            fd, temp_name = tempfile.mkstemp(prefix="artifact-", dir=self.tmp)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.replace(temp_name, destination)
                except PermissionError:
                    if not destination.exists():
                        raise
                    self._get_with_retry(ref)
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
            self._verify_manifest(ref)
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
                try:
                    os.replace(temp_name, manifest_path)
                except PermissionError:
                    if not manifest_path.exists():
                        raise
                    self._verify_manifest(ref)
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
        manifest_path = self.manifest_path_for(ref)
        if manifest_path.is_file():
            self._verify_manifest(ref)
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
        return sum(1 for path in self.objects.glob("*/*") if path.is_file())
