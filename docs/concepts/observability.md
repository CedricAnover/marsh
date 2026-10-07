# Observability

Marsh observability is a downstream projection of canonical runtime semantics. Observers can inspect execution without becoming a second scheduler, runtime, lifecycle authority, or recovery mechanism.

## Canonical correlation

Every runtime event may carry the following identities:

| Field | Meaning |
| --- | --- |
| `workflow_id` | Stable workflow identity. |
| `task_id` | Stable semantic task identity. |
| `execution_id` | Stable semantic execution identity; it survives retries. |
| `attempt_id` | Identity of one retry attempt; it changes for each attempt. |
| `provider_id` | Provider realization identity. |
| `process_id` | Process-lifetime identity. |
| `sequence` | Ordering evidence within one runtime observer stream. |
| `timestamp` | Operational timing evidence. |

Provider handles and process-local identifiers are evidence, not semantic execution identity.

## Event vocabulary

The runtime emits evidence for workflow/task lifecycle, provider admission, attempts, process lifecycle, result materialization, cancellation, and observation quality. Providers do not need to implement every event; the vocabulary defines shared semantics when evidence is available.

`UNKNOWN` and `AMBIGUOUS` states remain unresolved evidence. Observers must not turn missing evidence into success or failure.

## Diagnostics

Operational diagnostics use stable categories such as:

- `TIMEOUT_PROCESS` vs. `TIMEOUT_OBSERVATION`;
- `CANCELLATION_REQUESTED` vs. `CANCELLATION_CONFIRMED`;
- `PROVIDER_FAILURE` and `CAPABILITY_MISMATCH`;
- `PROVIDER_UNAVAILABLE`;
- `CLEANUP_FAILURE` and `OBSERVATION_FAILURE`;
- `UNKNOWN_STATE` and `AMBIGUOUS_STATE`;
- `ARTIFACT_VERIFICATION_FAILURE`.

These categories explain evidence; they do not redefine the canonical `Result` state.

## Redaction boundary

Events and diagnostics are recursively redacted before they reach observers. Sensitive keys include credentials, authorization values, tokens, API keys, passwords, and private keys. Bearer/basic authorization values are also redacted from text.

Safe operational fields such as identifiers, status, duration, sequence, event type, and provider names remain available.

Observer failures are isolated and cannot alter execution.

## Optional OpenTelemetry integration

`OpenTelemetryObserver` is an optional adapter around the OpenTelemetry **API**. Marsh does not configure an SDK or exporter and does not make OpenTelemetry a runtime dependency.

Install `opentelemetry-api` in the application environment when this adapter is desired. The application remains responsible for configuring the OpenTelemetry SDK/exporters. This follows the OpenTelemetry guidance for instrumenting libraries. Traces and metrics are stable in the current Python implementation; logs remain under development.

```python
from marsh import OpenTelemetryObserver, execute_workflow

observer = OpenTelemetryObserver()
execute_workflow(workflow, observers=(observer,))
```

## Example

```python
from marsh import EventType, Observer

class Printer(Observer):
    def on_event(self, event):
        print(event.to_dict())

execute_workflow(workflow, observers=(Printer(),))
```

The SDK remains the same for applications that do not need observability. Advanced users opt into observers without changing workflow definitions or scheduler semantics.
