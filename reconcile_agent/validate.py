"""
Deterministic validation and type coercion.

Everything here is pure and reproducible: no LLM, no randomness. Given the same
input and rule, you always get the same output. This is the half of the system
that makes results auditable, which is what regulated/enterprise buyers care about.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def coerce_value(raw: Any, target_type: str) -> Any:
    """Best-effort deterministic coercion. Returns None if it can't coerce cleanly."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None

    if target_type == "string":
        return s

    if target_type == "integer":
        cleaned = re.sub(r"[,_\s]", "", s)
        try:
            return int(float(cleaned))
        except ValueError:
            return None

    if target_type == "number":
        cleaned = re.sub(r"[,$_\s]", "", s)
        try:
            return float(cleaned)
        except ValueError:
            return None

    if target_type == "boolean":
        if s.lower() in {"true", "yes", "y", "1", "t", "active"}:
            return True
        if s.lower() in {"false", "no", "n", "0", "f", "inactive"}:
            return False
        return None

    if target_type == "date":
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%Y/%m/%d",
                    "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    if target_type == "email":
        return s.lower() if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s) else None

    return s


def validate_record(record: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Return a list of human-readable validation errors. Empty list = valid."""
    errors: list[str] = []
    fields = schema.get("fields", {})

    for name, spec in fields.items():
        value = record.get(name)
        required = spec.get("required", False)

        if value is None:
            if required:
                errors.append(f"missing required field '{name}'")
            continue

        expected = spec.get("type", "string")
        if not _type_ok(value, expected):
            errors.append(f"field '{name}' failed type '{expected}' (got {value!r})")

        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"field '{name}' value {value!r} not in allowed set {spec['enum']}")

    return errors


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected in ("date", "email"):
        return isinstance(value, str) and value != ""
    return True
