# Marsh documentation

This directory is the public documentation system for Marsh. The README is the concise
orientation and quick-start surface; the documentation tree carries progressively
deeper user and developer guidance.

## Start here

- [Workflow tutorial](tutorials/workflow.md) — learn the canonical Workflow API from a minimal example through planning, execution, results, and current boundaries.

## Concepts

- [Architecture](concepts/architecture.md) — implemented architectural boundaries and semantic ownership.
- [Semantic contract](concepts/semantic-contracts.md) — canonical semantic ownership, lifecycle, identity, capability, recovery, and conformance rules.
- [Artifacts and reproducibility](concepts/artifacts-and-reproducibility.md)
- [Observability](concepts/observability.md) — correlated runtime events, diagnostics, redaction, and optional telemetry integration. — execution/attempt/artifact identity, provenance, and content-addressed storage.

## How-to guides

- [API migration](how-to/migrate-api.md) — migrate incrementally from Conveyor, executors, and DAG APIs without a flag-day rewrite.

## Reference

- [CLI](reference/cli.md) — `marsh inspect`, deterministic JSON output, and `marsh plugins list`.
- [Extensions](reference/extensions.md) — `marsh.extensions` entry points and compatibility metadata.
- [Workflow IR](reference/workflow-ir.md) — the versioned `marsh.workflow/v1` canonical representation.
- [Remote execution](reference/remote-execution.md) — v0.4.1 machine, connection, substrate, agent, and reconciliation contracts.

## Releases

- [Observability & Operational Readiness](releases/observability.md) — current release observability contract and verification scope.

- [v0.4.1 — Remote Execution Readiness](releases/v0.4.1.md) — historical remote execution boundary.
- [v0.4.0 — Stable Workflow Kernel](releases/v0.4.0.md) — prior semantic-kernel release.
- [v0.3.9 — UX & Extension Convergence](releases/v0.3.9.md)
- [v0.3.8 — Artifacts & Reproducibility](releases/v0.3.8.md)

## Archive

Historical engineering audits and release-specific evaluations are retained for traceability:

- [v0.3.2 test portability audit](archive/v0.3.2-test-portability.md)
- [P0 repository audit](archive/p0-repository-audit.md)
- [P6 UX and composition evaluation](archive/p6-ux-composition-evaluation.md)

## Documentation rules

- Public behavior belongs in user-facing documentation, not only in release notes.
- Concepts explain semantics and boundaries.
- How-to guides explain how to accomplish a concrete task.
- Reference pages define commands, APIs, and compatibility contracts.
- Release pages record what changed and the evidence required to accept the release.
- Historical audits remain archived rather than competing with current public guidance.
