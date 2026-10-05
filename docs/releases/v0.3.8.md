# v0.3.8 — Artifacts & Reproducibility

## Highlights

- Added deterministic canonical execution identity based on the existing Workflow IR.
- Added SHA-256 content identity for artifacts.
- Added immutable Artifact and ArtifactRef contracts.
- Added allow-listed serializable Provenance.
- Added a local content-addressed ArtifactStore with manifests and integrity verification.
- Added additive execution/artifact/provenance fields to Result.
- Added opt-in runtime artifact materialization.
- Routed cache identity through the shared canonical primitives.
- Added fresh-process, concurrent, corruption, and cross-process reproducibility coverage.
- Preserved legacy callable and process-scheduler compatibility.

## Compatibility

Portable execution identity is available when workflow semantics cross the canonical serialization boundary. Legacy non-portable callables remain executable but do not receive a fabricated portable identity.

Artifact persistence is opt-in. Existing workflow execution does not require an artifact directory.

## Verification

Release acceptance requires:

- CircleCI build;
- CircleCI lint;
- Python 3.10, 3.11, and 3.12 tests;
- CircleCI integration;
- Windows portability checks where configured;
- package build and artifact inspection;
- security review;
- exact artifact hashes;
- main/develop synchronization.

Upstash Box is intentionally reserved for the final tag/release step and is not used during normal development.
