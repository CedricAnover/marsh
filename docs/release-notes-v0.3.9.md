# Marsh v0.3.9 — UX & Extension Convergence

v0.3.9 adds a small, dependency-free application boundary around the canonical
workflow/runtime semantics.

## CLI inspection

The marsh CLI is read-only for inspection:

    marsh inspect workflow.json
    marsh inspect workflow.json --json

Inspection validates and plans the workflow but never executes it. Machine-readable
output is deterministic JSON.

## Extension discovery

Optional integrations can advertise entry points in the marsh.extensions group.
Discovery is deterministic and sorted by extension name/value. Extensions must
declare Marsh-Extension-Contract metadata matching the current contract version.

An incompatible extension is rejected before loading. The core package remains
dependency-light when no extension is installed.

## Diagnostics

CLI diagnostics redact credential-like mapping keys and common authorization values.
Applications should treat diagnostics as safe-to-display output, but should still
avoid deliberately passing secrets into workflow metadata.

## Compatibility

v0.3.9 distinguishes the Marsh package version, extension contract version,
workflow IR version, and extension package version. Only the extension contract
controls activation compatibility.

## Scope boundary

v0.3.9 does not add remote execution, a new scheduler, a generalized plugin
framework, or a second workflow semantic model.
