# Marsh CLI inspection

The v0.3.9 CLI intentionally provides read-only surfaces.

## Commands

- marsh --version — report the installed Marsh package version.
- marsh inspect <workflow.json> — validate and inspect deterministic plan state.
- marsh inspect <workflow.json> --json — emit stable machine-readable JSON.
- marsh plugins list — inspect discovered extensions.
- marsh plugins list --json — emit extension discovery records as JSON.

The inspect command reports:

- workflow identity;
- task count and IDs;
- deterministic execution order;
- initially-ready tasks;
- portable execution identity when available;
- explicit confirmation that execution was not performed.

The CLI does not expose provider credentials, raw environment configuration, or
execution controls.
