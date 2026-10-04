"""Semantic identifier validation for the canonical Workflow IR."""

from __future__ import annotations

import re

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


def validate_semantic_id(value: str, kind: str) -> str:
    """Validate an identifier that must survive serialization unchanged."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{kind} id must be non-empty")
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"{kind} id {value!r} must contain only letters, numbers, "
            "periods, underscores, colons, and hyphens"
        )
    return value
