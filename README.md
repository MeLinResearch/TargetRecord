# reconcile

**A self-correcting agent that maps messy real-world records onto a clean target schema, validates its own output, and escalates what it can't fix.**

Every enterprise dataset is a mess: inconsistent column names, mixed date formats, currency symbols glued to numbers, the occasional invalid email or corrupted row. The boring, expensive, manual job is reconciling that into something a downstream system will accept. `reconcile` automates the judgment part and keeps the data-handling part deterministic and auditable.

```
$ python -m examples.run_demo

Loaded 6 messy records.

=== AGENT RUN ===
{
  "success_rate": 0.667,
  "rounds_used": 1,
  "clean_count": 4,
  "failed_count": 2,
  ...
}

=== CLEAN RECORDS ===
{"full_name": "Jane Doe", "email": "jane@example.com", "amount": 1250.0, "signup_date": "2024-01-15", ...}
...

=== STILL FAILING (flagged for human review) ===
{"record": {"E-Mail": "not-an-email", ...}, "errors": ["missing required field 'email'"]}
```

It cleaned the four fixable records and flagged the two it shouldn't touch: a genuinely invalid email and a corrupted row. It does not silently mangle bad data.

## How it works

```
messy records ──┐
                ├──> [LLM proposes a field mapping]   <- ambiguous judgment
target schema ──┘            │
                             v
                  [deterministic transform]           <- pure, reproducible
                             │
                             v
                  [validate against schema]
                             │
                   pass ─────┴───── fail
                    │                 │
                 clean output    feed failures back, re-propose (up to N rounds)
                                       │
                            still failing ──> escalate to human review
```

The key design decision: **the LLM only proposes the mapping. It never touches the data.** All coercion and validation are deterministic, so the same input always produces the same output and every transformation is auditable.

## Run it

No API key required. The mapping proposer falls back to a deterministic heuristic matcher so the demo runs offline:

```bash
git clone <https://github.com/MeLinResearch/Reconcile.git>
cd reconcile
python -m examples.run_demo
```

To use Claude for the mapping step:

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-...
python -m examples.run_demo
```

## Use it on your own data

```python
from reconcile_agent import reconcile

result = reconcile(
    records,
    target_schema,
    max_rounds=3,
)

print(result.success_rate)
result.clean_records
result.failed_records
result.mapping
```

Supported target types: `string`, `integer`, `number`, `boolean`, `date` normalized to ISO `YYYY-MM-DD`, and `email`. Field specs support `required` and `enum`.

## Why this exists

Built as a compact demonstration of the pattern behind production data-integration agents: let a model handle ambiguous mapping judgment, keep the actual data transformation deterministic and reproducible, validate everything, and surface what can't be resolved instead of guessing.

## License

MIT
