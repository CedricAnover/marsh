"""Secret-safe diagnostics for CLI and extension-facing surfaces."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

_SECRET_KEY = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|credential|private[_-]?key)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(bearer\s+)[A-Za-z0-9._~+/=-]+|(basic\s+)[A-Za-z0-9+/=]+",
    re.IGNORECASE,
)


def redact_text(value: str, *, secrets: tuple[str, ...] = ()) -> str:
    result = value
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return _SECRET_VALUE.sub(r"\1[REDACTED]", result)


def redact(value: Any, *, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _SECRET_KEY.search(str(key)) else redact(
                item, secrets=secrets
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets=secrets) for item in value]
    if isinstance(value, str):
        return redact_text(value, secrets=secrets)
    return value


@dataclass(frozen=True)
class DiagnosticReport:
    code: str
    severity: str
    message: str
    details: Mapping[str, Any] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": redact_text(self.message),
            "details": redact(self.details),
        }


def diagnostic(
    code: str,
    message: str,
    *,
    severity: str = "info",
    details: Mapping[str, Any] | None = None,
) -> DiagnosticReport:
    if severity not in {"info", "warning", "error"}:
        raise ValueError("severity must be info, warning, or error")
    return DiagnosticReport(code, severity, message, details or {})
