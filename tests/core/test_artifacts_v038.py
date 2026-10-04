import json

import pytest

from marsh.core.artifacts import Artifact, Provenance
from marsh.core.artifact_store import LocalArtifactStore


def test_artifact_identity_is_content_addressed():
    store = LocalArtifactStore()
    first = store.put(b"hello", media_type="text/plain")
    second = store.put(b"hello", media_type="application/octet-stream")

    assert first.digest == second.digest
    assert first.size == 5
    assert store.get(first) == b"hello"


def test_artifact_store_detects_modified_content(tmp_path):
    store = LocalArtifactStore(tmp_path)
    ref = store.put(b"immutable")
    object_path = store.path_for(ref)
    object_path.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="digest|integrity"):
        store.get(ref)


def test_artifact_store_deduplicates_identical_content(tmp_path):
    store = LocalArtifactStore(tmp_path)

    first = store.put(b"same")
    second = store.put(b"same")

    assert first.digest == second.digest
    assert store.object_count() == 1


def test_provenance_is_allow_listed_and_serializable():
    provenance = Provenance(
        schema_version=1,
        workflow_id="wf",
        workflow_version="1",
        task_id="task",
        execution_id="exec",
        attempt_id="task:1",
        operation_ref={"kind": "python_callable", "module": "tests", "qualname": "run"},
        provider_fingerprint="provider-hash",
        policy_fingerprint="policy-hash",
    )

    encoded = provenance.to_dict()
    assert "execution_id" in encoded
    assert "provider_fingerprint" in encoded
    assert "environment" not in encoded
    assert json.dumps(encoded, sort_keys=True)


def test_artifact_references_are_immutable():
    ref = Artifact(
        digest="sha256:abc",
        size=3,
        media_type="text/plain",
    )
    with pytest.raises(Exception):
        ref.digest = "sha256:def"
