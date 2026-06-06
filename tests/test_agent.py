import sys
from pathlib import Path

# The repo is currently an uninstalled flat source tree, so keep pytest imports local to the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from copy import deepcopy

from reconcile_agent import reconcile


TARGET_SCHEMA = {
    "fields": {
        "full_name": {"type": "string", "required": True},
        "email": {"type": "email", "required": True},
        "amount": {"type": "number", "required": True},
        "active": {"type": "boolean", "required": True},
    }
}

GOOD_MAPPING = {
    "full_name": {"source": "Name", "type": "string"},
    "email": {"source": "Email", "type": "email"},
    "amount": {"source": "Total", "type": "number"},
    "active": {"source": "Status", "type": "boolean"},
}


class StaticProposer:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.mapping


class SequenceProposer:
    def __init__(self, mappings):
        self.mappings = list(mappings)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.mappings[len(self.calls) - 1]


def test_clean_records_are_transformed_successfully():
    records = [
        {"Name": "Jane Doe", "Email": "JANE@EXAMPLE.COM", "Total": "$1,250.00", "Status": "yes"},
        {"Name": "John Smith", "Email": "john@example.com", "Total": "25", "Status": "0"},
    ]

    result = reconcile(records, TARGET_SCHEMA, propose=StaticProposer(GOOD_MAPPING))

    assert result.clean_records == [
        {"full_name": "Jane Doe", "email": "jane@example.com", "amount": 1250.0, "active": True},
        {"full_name": "John Smith", "email": "john@example.com", "amount": 25.0, "active": False},
    ]
    assert result.failed_records == []
    assert result.rounds_used == 1
    assert result.success_rate == 1.0


def test_invalid_records_are_separated_with_auditable_failure_information():
    records = [
        {"Name": "Jane Doe", "Email": "jane@example.com", "Total": "10", "Status": "true"},
        {"Name": "Bad Email", "Email": "not-an-email", "Total": "$1,250.00", "Status": "yes"},
    ]

    result = reconcile(records, TARGET_SCHEMA, max_rounds=1, propose=StaticProposer(GOOD_MAPPING))

    assert result.clean_records == [
        {"full_name": "Jane Doe", "email": "jane@example.com", "amount": 10.0, "active": True}
    ]
    assert result.failed_records == [
        {
            "_record": {"Name": "Bad Email", "Email": "not-an-email", "Total": "$1,250.00", "Status": "yes"},
            "_errors": ["missing required field 'email'"],
            "_partial": {"full_name": "Bad Email", "email": None, "amount": 1250.0, "active": True},
        }
    ]


def test_missing_required_field_does_not_silently_pass_or_get_invented():
    records = [{"Email": "missing-name@example.com", "Total": "100", "Status": "true"}]

    result = reconcile(records, TARGET_SCHEMA, max_rounds=1, propose=StaticProposer(GOOD_MAPPING))

    assert result.clean_records == []
    assert result.failed_records == [
        {
            "_record": {"Email": "missing-name@example.com", "Total": "100", "Status": "true"},
            "_errors": ["missing required field 'full_name'"],
            "_partial": {"full_name": None, "email": "missing-name@example.com", "amount": 100.0, "active": True},
        }
    ]


def test_input_records_are_not_mutated_in_place():
    records = [{"Name": "Jane Doe", "Email": "jane@example.com", "Total": "$1,250.00", "Status": "yes"}]
    original_records = deepcopy(records)

    result = reconcile(records, TARGET_SCHEMA, propose=StaticProposer(GOOD_MAPPING))

    assert result.clean_records == [
        {"full_name": "Jane Doe", "email": "jane@example.com", "amount": 1250.0, "active": True}
    ]
    assert records == original_records


def test_retry_uses_failure_feedback_and_accepts_corrected_mapping():
    bad_mapping = {
        **GOOD_MAPPING,
        "email": {"source": "Missing Email Column", "type": "email"},
    }
    proposer = SequenceProposer([bad_mapping, GOOD_MAPPING])
    records = [{"Name": "Jane Doe", "Email": "jane@example.com", "Total": "10", "Status": "true"}]

    result = reconcile(records, TARGET_SCHEMA, max_rounds=2, propose=proposer)

    assert result.clean_records == [
        {"full_name": "Jane Doe", "email": "jane@example.com", "amount": 10.0, "active": True}
    ]
    assert result.failed_records == []
    assert result.rounds_used == 2
    assert proposer.calls[0]["previous_mapping"] is None
    assert proposer.calls[0]["failures"] is None
    assert proposer.calls[1]["previous_mapping"] == bad_mapping
    assert proposer.calls[1]["failures"] == [{"Name": "Jane Doe", "Email": "jane@example.com", "Total": "10", "Status": "true"}]
