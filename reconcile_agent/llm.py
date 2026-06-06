"""
LLM mapping proposer.

The LLM's ONLY job: look at sample messy records + the target schema and propose
a field mapping. It never sees or rewrites the full dataset, and it never does the
actual coercion. That keeps the data transformation deterministic and auditable.

If ANTHROPIC_API_KEY is set, this calls Claude. If not, it falls back to a
deterministic heuristic matcher so the demo runs out of the box with no key.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


def propose_mapping(
    *,
    sample: list[dict[str, Any]],
    target_schema: dict[str, Any],
    previous_mapping: dict[str, Any] | None = None,
    failures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _propose_with_claude(sample, target_schema, previous_mapping, failures)
        except Exception as exc:
            print(f"[llm] Claude call failed ({exc}); using heuristic fallback")
    return _propose_heuristic(sample, target_schema)


def _propose_with_claude(sample, target_schema, previous_mapping, failures):
    import anthropic

    client = anthropic.Anthropic()
    correction = ""
    if previous_mapping and failures:
        correction = (
            "\nYour previous mapping produced these failing records. "
            "Fix the mapping so they validate:\n"
            f"previous_mapping = {json.dumps(previous_mapping)}\n"
            f"failures = {json.dumps(failures[:5])}\n"
        )

    prompt = (
        "You map messy source records onto a target schema. "
        "Return ONLY JSON: an object whose keys are target field names and whose "
        'values are {"source": "<source field name>", "type": "<target type>"}. '
        "No prose, no markdown fences.\n\n"
        f"TARGET SCHEMA:\n{json.dumps(target_schema, indent=2)}\n\n"
        f"SAMPLE SOURCE RECORDS:\n{json.dumps(sample, indent=2)}\n"
        f"{correction}"
    )

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def _propose_heuristic(sample, target_schema) -> dict[str, Any]:
    source_fields = set()
    for rec in sample:
        source_fields.update(k for k in rec.keys() if k is not None)

    mapping: dict[str, Any] = {}
    for target_field, spec in target_schema.get("fields", {}).items():
        best = _best_source_match(target_field, source_fields)
        mapping[target_field] = {"source": best, "type": spec.get("type", "string")}
    return mapping


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


_SYNONYMS = {
    "email": {"emailaddress", "mail", "contactemail", "e"},
    "fullname": {"name", "customername", "client", "fullname"},
    "amount": {"total", "price", "cost", "value", "amt"},
    "signupdate": {"created", "createdat", "joined", "date", "registered"},
    "active": {"isactive", "status", "enabled"},
}


def _best_source_match(target_field: str, source_fields: set[str]) -> str | None:
    nt = _normalize(target_field)
    norm_sources = {_normalize(s): s for s in source_fields}

    if nt in norm_sources:
        return norm_sources[nt]
    for ns, original in norm_sources.items():
        # Substring matches are intentionally conservative to avoid fields like
        # "e" matching "email" or arbitrary source names containing one letter.
        if len(nt) > 1 and len(ns) > 1 and (nt in ns or ns in nt):
            return original
    for syn in _SYNONYMS.get(nt, set()):
        if len(syn) > 1 and syn in norm_sources:
            return norm_sources[syn]
        for ns, original in norm_sources.items():
            if len(syn) > 1 and syn in ns:
                return original
    return None
