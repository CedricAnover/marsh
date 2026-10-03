"""Redact sensitive metadata from runtime events before observers receive them."""

from marsh import EventType, ProcessStatus, RuntimeEvent, emit_event


class Collector:
    def __init__(self):
        self.events = []

    def on_event(self, event):
        self.events.append(event)


collector = Collector()
event = RuntimeEvent(
    sequence=1,
    event_type=EventType.TASK_COMPLETED,
    workflow_id="secure-demo",
    task_id="hello",
    status=ProcessStatus.COMPLETED,
    metadata={"token": "do-not-log", "duration": 0.01},
)
emit_event(collector, event)

received = collector.events[0]
assert received.metadata["token"] == "[REDACTED]"
assert received.metadata["duration"] == 0.01
print(received.metadata)
