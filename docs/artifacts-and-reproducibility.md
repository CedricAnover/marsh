# Artifacts and Reproducibility

## Scope

v0.3.8 adds a small provider-independent artifact and identity layer around the existing Workflow runtime.

It does not add a second scheduler, a distributed control plane, a mandatory remote object store, or a new CLI.

## Identity model

Marsh distinguishes four concepts:

- **Execution identity** — a SHA-256 fingerprint of canonical portable workflow semantics.
- **Attempt identity** — the runtime identity of one execution attempt. Retries create new attempt identities.
- **Artifact identity** — a SHA-256 digest of artifact bytes. It is independent of storage location.
- **Result** — the semantic execution outcome, which may reference artifacts and provenance.

The identities must not be conflated. In particular, a retry does not change the logical execution identity, and moving an artifact does not change its artifact identity.

## Canonical execution identity

Portable execution identity is derived from the existing canonical Workflow IR serializer.

The identity boundary uses:

- deterministic UTF-8 JSON;
- sorted mapping keys and compact separators for generic identity payloads;
- explicit schema/version markers;
- rejection of non-finite numeric values;
- explicit rejection of unsupported runtime objects.

Legacy workflows containing non-portable local callables remain executable. If a workflow cannot cross the canonical serialization boundary, Marsh does not fabricate a supposedly portable identity from process-local object representations.

## Result fields

Canonical Result values may include:

- execution_id;
- attempt_id;
- artifact_refs;
- provenance.

These fields are additive. Existing stdout, stderr, status, error, duration, metadata, and ok behavior remain the primary result semantics.

## ArtifactStore

LocalArtifactStore is content-addressed:

    <root>/
        objects/
            <first-two-digest-characters>/
                <remaining-digest>
        manifests/
            <full-digest>.json
        tmp/

Writes use temporary files and atomic finalization. Existing objects are verified rather than silently accepted as valid. Reads verify both declared size and SHA-256 content identity, and manifest corruption is rejected.

Identical bytes deduplicate to the same content identity.

Artifact persistence is opt-in. The normal runtime does not create an artifact directory unless an ArtifactStore is supplied.

## Provenance

Provenance is an explicit allow-list rather than an environment dump.

The current contract can include:

- schema version;
- workflow and task identity;
- execution and attempt identity;
- parent execution references;
- operation reference;
- provider, machine, and policy fingerprints where relevant;
- input and output artifact references;
- creation time.

Credentials, full environment variables, arbitrary provider objects, process-local objects, and storage implementation details are not portable provenance.

## Cache semantics

The existing cache boundary remains authoritative.

Cache identity uses the shared canonical identity primitives rather than a separate serialization/hash implementation.

A successful cache hit reuses the cached Result and therefore does not create a new attempt. Corrupt or unverifiable artifact data must not be treated as a valid artifact.

## Reproducibility verification

v0.3.8 tests identity and artifact behavior across:

- fresh Python processes;
- repeated canonicalization;
- bounded concurrent artifact writes;
- artifact reopen/read from another process;
- manifest corruption;
- Python 3.10, 3.11, and 3.12 CI;
- Windows portability CI where the existing workflow permits it.

Reproducibility is a tested property, not an assumption based on implementation intent.

## Compatibility

The canonical runtime keeps the existing scheduler, policy, provider, and execution seams. Artifact storage is optional and is kept outside process-worker state; process workers return normal Results and the parent runtime may materialize artifacts.

This preserves the existing process-scheduler boundary while allowing the same artifact contract to be used by sequential, thread, async, and process execution modes.

## Security considerations

Before release, review:

1. canonicalization for accidental secret inclusion;
2. provenance allow-list completeness;
3. artifact path validation and traversal resistance;
4. digest and size verification;
5. atomic write behavior under concurrency;
6. temporary-file cleanup;
7. cache behavior on corrupt or stale data;
8. release artifacts and hashes.

## Non-goals

v0.3.8 does not attempt to provide:

- remote object storage;
- distributed cache invalidation;
- arbitrary callable serialization;
- cross-machine execution orchestration;
- automatic task-to-task dataflow;
- a general artifact retention/garbage-collection policy.
