"""
Demo: reconcile messy_records.csv onto target_schema.json.

Run from the repo root:
    python -m examples.run_demo

Works with no API key. Set ANTHROPIC_API_KEY to use Claude for the mapping proposal step.
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reconcile_agent import reconcile, to_json


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    records = load_csv(os.path.join(here, "messy_records.csv"))
    with open(os.path.join(here, "target_schema.json"), encoding="utf-8") as f:
        schema = json.load(f)

    print(f"Loaded {len(records)} messy records.\n")
    result = reconcile(records, schema, max_rounds=3)

    print("=== AGENT RUN ===")
    print(to_json(result))

    print("\n=== CLEAN RECORDS ===")
    for r in result.clean_records:
        print(json.dumps(r))

    if result.failed_records:
        print("\n=== STILL FAILING (flagged for human review) ===")
        for f in result.failed_records:
            print(json.dumps({"record": f["_record"], "errors": f["_errors"]}))


if __name__ == "__main__":
    main()
