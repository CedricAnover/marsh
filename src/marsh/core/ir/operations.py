"""Explicit operation references and safe reconstruction."""

from __future__ import annotations

import importlib
from typing import Any

from marsh.core.ir.errors import OperationResolutionError
from marsh.core.ir.models import OperationRef


def operation_to_ref(operation: Any) -> OperationRef:
    """Convert an importable callable into an explicit operation reference."""
    if not callable(operation):
        raise TypeError(f"operation is not a callable: {type(operation).__name__}")
    module = getattr(operation, "__module__", None)
    qualname = getattr(operation, "__qualname__", None)
    if not module or not qualname:
        raise OperationResolutionError("callable does not expose module/qualname")
    if module == "__main__" or "<locals>" in qualname or qualname == "<lambda>":
        raise OperationResolutionError(
            "callable must be a top-level importable function outside __main__"
        )
    return OperationRef("python_callable", module, qualname)


def resolve_operation(reference: OperationRef) -> Any:
    """Resolve an explicit operation reference without evaluating serialized code."""
    try:
        module = importlib.import_module(reference.module)
        value: Any = module
        for part in reference.qualname.split("."):
            value = getattr(value, part)
    except (ImportError, AttributeError) as exc:
        raise OperationResolutionError(
            f"cannot resolve operation {reference.module}.{reference.qualname}"
        ) from exc
    if not callable(value):
        raise OperationResolutionError(
            f"resolved operation {reference.module}.{reference.qualname} is not callable"
        )
    return value
