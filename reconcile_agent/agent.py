"""
Schema-reconciliation agent.

The loop, in plain terms:
  1. Look at a sample of messy input records and the target schema.
  2. Ask an LLM to PROPOSE a field mapping.
  3. Apply that mapping deterministically to every record.
  4. Validate every transformed record against the target schema.
  5. If records fail, feed the failures back to the LLM, get a corrected mapping, and retry.
  6. Stop when everything validates or we hit max_rounds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from .validate import validate_record, coerce_value
from .llm import propose_mapping


@dataclass
class ReconcileResult:
    mapping: dict[str, Any]
    clean_records: list[dict[str, Any]]
    failed_records: list[dict[str, Any]]
    rounds_used: int
    log: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = len(self.clean_records) + len(self.failed_records)
        return len(self.clean_records) / total if total else 0.0


def reconcile(
    records: list[dict[str, Any]],
    target_schema: dict[str, Any],
    *,
    max_rounds: int = 3,
    sample_size: int = 8,
    propose: Callable[..., dict[str, Any]] = propose_mapping,
) -> ReconcileResult:
    """Reconcile messy `records` to `target_schema`. Returns a ReconcileResult."""
    log: list[str] = []
    mapping: dict[str, Any] = {}
    failures_for_feedback: list[dict[str, Any]] = []
    clean: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for round_num in range(1, max_rounds + 1):
        sample = records[:sample_size]
        mapping = propose(
            sample=sample,
            target_schema=target_schema,
            previous_mapping=mapping or None,
            failures=failures_for_feedback or None,
        )
        log.append(f"round {round_num}: proposed mapping for {len(mapping)} target fields")

        clean, failed = _apply_and_validate(records, mapping, target_schema)
        log.append(
            f"round {round_num}: {len(clean)} ok, {len(failed)} failed "
            f"({len(clean) / max(len(records), 1):.0%})"
        )

        if not failed:
            return ReconcileResult(mapping, clean, [], round_num, log)

        failures_for_feedback = [f["_record"] for f in failed[:sample_size]]

    return ReconcileResult(mapping, clean, failed, max_rounds, log)


def _apply_and_validate(
    records: list[dict[str, Any]],
    mapping: dict[str, Any],
    target_schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    clean: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for rec in records:
        transformed: dict[str, Any] = {}
        for target_field, rule in mapping.items():
            source_field = rule.get("source")
            target_type = rule.get("type", "string")
            raw = rec.get(source_field) if source_field else None
            transformed[target_field] = coerce_value(raw, target_type)

        errors = validate_record(transformed, target_schema)
        if errors:
            failed.append({"_record": rec, "_errors": errors, "_partial": transformed})
        else:
            clean.append(transformed)

    return clean, failed


def to_json(result: ReconcileResult) -> str:
    return json.dumps(
        {
            "mapping": result.mapping,
            "success_rate": round(result.success_rate, 3),
            "rounds_used": result.rounds_used,
            "clean_count": len(result.clean_records),
            "failed_count": len(result.failed_records),
            "log": result.log,
        },
        indent=2,
    )
