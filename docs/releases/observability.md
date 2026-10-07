# Observability & Operational Readiness

This release makes runtime observability a correlated, secret-safe projection of Marsh's canonical execution semantics.

## Added

- Correlated `RuntimeEvent` identity for workflow, task, execution, attempt, provider, and process boundaries.
- Explicit runtime event vocabulary for provider admission, attempts, process lifecycle, result materialization, cancellation, and observation quality.
- Stable operational diagnostic categories for timeout, cancellation, provider failure, capability mismatch, cleanup, observation, ambiguity, and artifact verification.
- Recursive redaction before observer delivery, including sensitive mapping keys and authorization values.
- Observer isolation so observer exceptions cannot change execution outcomes.
- Optional `OpenTelemetryObserver` integration through the OpenTelemetry API without adding a mandatory runtime dependency or exporter configuration.
- Documentation and conformance coverage for retry identity continuity and cross-boundary correlation.

## Compatibility

The existing `Observer.on_event()` contract remains valid. Existing event constructors remain source-compatible because new correlation fields are optional.

Execution identity continues across retries while attempt identity changes per retry. Provider and process identities remain distinct from semantic execution identity.

## Verification

Release verification covers unit and integration tests, documentation consistency, package build, optional-dependency isolation, secret-redaction checks, scheduler correlation, and CI across the supported Python versions.

## Scope

No second runtime or scheduler, distributed control plane, mandatory telemetry backend, or provider-specific observability semantics were introduced.
