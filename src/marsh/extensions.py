"""Deterministic discovery and compatibility for optional Marsh extensions."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any

EXTENSION_ENTRY_POINT_GROUP = "marsh.extensions"
EXTENSION_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class ExtensionInfo:
    name: str
    package: str | None
    package_version: str | None
    contract_version: int | None
    value: str
    status: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "package": self.package,
            "package_version": self.package_version,
            "contract_version": self.contract_version,
            "value": self.value,
            "status": self.status,
            "reason": self.reason,
        }


def _selected_entry_points() -> tuple[Any, ...]:
    entry_points = metadata.entry_points()
    if hasattr(entry_points, "select"):
        selected = entry_points.select(group=EXTENSION_ENTRY_POINT_GROUP)
    else:  # pragma: no cover - Python 3.10 compatibility path
        selected = entry_points.get(EXTENSION_ENTRY_POINT_GROUP, ())
    return tuple(sorted(selected, key=lambda item: (item.name, item.value)))


def _contract_version(entry_point: Any) -> int | None:
    distribution = entry_point.dist
    if distribution is None:
        return None
    raw = distribution.metadata.get("Marsh-Extension-Contract")
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def discover_extensions() -> tuple[ExtensionInfo, ...]:
    """Discover extensions without importing extension code."""
    result: list[ExtensionInfo] = []
    seen: set[str] = set()

    for entry_point in _selected_entry_points():
        distribution = entry_point.dist
        package = distribution.name if distribution is not None else None
        package_version = distribution.version if distribution is not None else None
        contract = _contract_version(entry_point)

        if entry_point.name in seen:
            status = "duplicate"
            reason = "duplicate extension identity"
        elif contract is None:
            status = "malformed"
            reason = "missing or invalid Marsh-Extension-Contract metadata"
        elif contract != EXTENSION_CONTRACT_VERSION:
            status = "unsupported"
            reason = (
                f"extension contract {contract} is incompatible with "
                f"Marsh contract {EXTENSION_CONTRACT_VERSION}"
            )
        else:
            status = "compatible"
            reason = None

        seen.add(entry_point.name)
        result.append(
            ExtensionInfo(
                name=entry_point.name,
                package=package,
                package_version=package_version,
                contract_version=contract,
                value=entry_point.value,
                status=status,
                reason=reason,
            )
        )
    return tuple(result)


def load_compatible_extensions() -> tuple[Any, ...]:
    """Load only extensions that passed the compatibility gate."""
    loaded: list[Any] = []
    for info, entry_point in zip(
        discover_extensions(),
        _selected_entry_points(),
        strict=False,
    ):
        if info.status != "compatible":
            continue
        loaded.append(entry_point.load())
    return tuple(loaded)


__all__ = [
    "EXTENSION_CONTRACT_VERSION",
    "EXTENSION_ENTRY_POINT_GROUP",
    "ExtensionInfo",
    "discover_extensions",
    "load_compatible_extensions",
]
