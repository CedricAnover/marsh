"""Structured, deterministic diagnostics for workflow validation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    severity: str = "error"
    task_id: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in {"error", "warning", "info"}:
            raise ValueError("diagnostic severity must be error, warning, or info")
