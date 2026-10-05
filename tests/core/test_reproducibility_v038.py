import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from marsh.core.artifact_store import LocalArtifactStore
from marsh.core.domain import ProcessSpec, Task, Workflow


def test_execution_identity_is_stable_across_fresh_processes():
    script = """
import json, sys
from marsh.core.domain import ProcessSpec, Task, Workflow
from marsh.core.identity import execution_id
workflow = Workflow(
    id="cross-process",
    inputs={"b": 2, "a": 1},
    tasks=(Task(id="run", operation=ProcessSpec(sys.executable, ("-c", "print(1)"))),),
)
print(execution_id(workflow))
"""
    first = subprocess.check_output([sys.executable, "-c", script], text=True).strip()
    second = subprocess.check_output([sys.executable, "-c", script], text=True).strip()

    assert first == second


def test_artifact_store_is_safe_under_bounded_concurrent_deduplication(tmp_path):
    store = LocalArtifactStore(tmp_path)

    def put_once(_):
        return store.put(b"concurrent")

    with ThreadPoolExecutor(max_workers=4) as executor:
        refs = list(executor.map(put_once, range(8)))

    assert {ref.digest for ref in refs} == {refs[0].digest}
    assert store.object_count() == 1
    assert store.verify(refs[0])


def test_artifact_manifest_corruption_is_detected(tmp_path):
    store = LocalArtifactStore(tmp_path)
    ref = store.put(b"manifest")
    manifest = store.manifest_path_for(ref)
    manifest.write_text(
        json.dumps({"digest": ref.digest, "size": 999, "media_type": ref.media_type}),
        encoding="utf-8",
    )

    try:
        store.get(ref)
    except ValueError as exc:
        assert "manifest" in str(exc)
    else:
        raise AssertionError("corrupt manifest was accepted")


def test_artifact_store_can_reopen_reference_in_a_new_process(tmp_path):
    store = LocalArtifactStore(tmp_path)
    ref = store.put(b"cross-process artifact")

    script = """
import sys
from marsh.core.artifact_store import LocalArtifactStore
from marsh.core.artifacts import Artifact
store = LocalArtifactStore(sys.argv[1])
ref = Artifact(digest=sys.argv[2], size=int(sys.argv[3]), media_type=sys.argv[4])
assert store.get(ref) == b"cross-process artifact"
"""
    subprocess.check_call(
        [
            sys.executable,
            "-c",
            script,
            str(tmp_path),
            ref.digest,
            str(ref.size),
            ref.media_type,
        ]
    )


def test_artifact_store_recovers_when_windows_replace_reports_access_denied_after_deduplication(tmp_path, monkeypatch):
    store = LocalArtifactStore(tmp_path)
    original_replace = __import__("marsh.core.artifact_store", fromlist=["os"]).os.replace
    destination_created = False

    def replace_with_windows_collision(temp_name, destination):
        nonlocal destination_created
        if not destination_created and str(temp_name).startswith(str(store.tmp / "artifact-")):
            destination.write_bytes(__import__("pathlib").Path(temp_name).read_bytes())
            destination_created = True
            raise PermissionError(5, "Access is denied")
        return original_replace(temp_name, destination)

    monkeypatch.setattr("marsh.core.artifact_store.os.replace", replace_with_windows_collision)

    ref = store.put(b"windows deduplication")

    assert store.verify(ref)
    assert store.object_count() == 1


def test_artifact_store_retries_transient_manifest_read_lock(tmp_path, monkeypatch):
    store = LocalArtifactStore(tmp_path)
    ref = store.put(b"manifest lock")
    manifest = store.manifest_path_for(ref)
    original_read_text = manifest.read_text
    attempts = 0

    def read_text_with_transient_lock(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(13, "Access is denied")
        return original_read_text(*args, **kwargs)

    monkeypatch.setattr(manifest, "read_text", read_text_with_transient_lock)
    assert store.get(ref) == b"manifest lock"
    assert attempts == 3
