"""Provider-independent data structures for marsh.workflow/v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

IR_NAME = "marsh.workflow"
IR_VERSION = 1


@dataclass(frozen=True)
class OperationRef:
    """Explicit reference to an executable Python operation."""

    kind: str
    module: str
    qualname: str

    def __post_init__(self) -> None:
        if self.kind != "python_callable":
            raise ValueError(f"unsupported operation reference kind: {self.kind!r}")
        if not self.module or not self.qualname:
            raise ValueError("operation reference requires module and qualname")
        if "<locals>" in self.qualname or self.qualname == "<lambda>":
            raise ValueError("local and lambda callables are not portable")


@dataclass(frozen=True)
class WorkflowIR:
    """Canonical semantic workflow representation."""

    id: str
    tasks: tuple[Mapping[str, Any], ...] = ()
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDocument:
    """Versioned envelope around a canonical workflow."""

    schema: Mapping[str, Any]
    workflow: Mapping[str, Any]
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema.get("name") != IR_NAME:
            raise ValueError(f"unsupported schema name: {self.schema.get('name')!r}")
