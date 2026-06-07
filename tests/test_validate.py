import sys
from pathlib import Path

# The repo is currently an uninstalled flat source tree, so keep pytest imports local to the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reconcile_agent.validate import coerce_value, validate_record


def test_number_and_currency_coercion_for_number_and_integer_fields():
    amount = coerce_value("$1,250.00", "number")
    count = coerce_value("1,250", "integer")
    currency_count = coerce_value("$1,250.00", "integer")

    assert amount == 1250.0
    assert validate_record({"amount": amount}, {"fields": {"amount": {"type": "number", "required": True}}}) == []
    assert count == 1250
    assert currency_count == 1250
    assert validate_record({"count": count}, {"fields": {"count": {"type": "integer", "required": True}}}) == []


def test_integer_coercion_rejects_fractional_values_instead_of_truncating():
    count = coerce_value("1.9", "integer")

    assert count is None
    assert validate_record({"count": count}, {"fields": {"count": {"type": "integer", "required": True}}}) == [
        "missing required field 'count'"
    ]


def test_bad_email_fails_validation_after_coercion():
    email = coerce_value("not-an-email", "email")
    errors = validate_record({"email": email}, {"fields": {"email": {"type": "email", "required": True}}})

    assert email is None
    assert errors == ["missing required field 'email'"]


def test_missing_required_field_fails_validation():
    errors = validate_record({}, {"fields": {"customer_name": {"type": "string", "required": True}}})

    assert errors == ["missing required field 'customer_name'"]


def test_boolean_coercion_accepts_supported_true_and_false_values():
    true_values = ["true", "yes", "1"]
    false_values = ["false", "no", "0"]

    for raw in true_values:
        coerced = coerce_value(raw, "boolean")
        assert coerced is True
        assert validate_record({"active": coerced}, {"fields": {"active": {"type": "boolean"}}}) == []

    for raw in false_values:
        coerced = coerce_value(raw, "boolean")
        assert coerced is False
        assert validate_record({"active": coerced}, {"fields": {"active": {"type": "boolean"}}}) == []


def test_date_validation_normalizes_valid_dates_and_rejects_invalid_dates():
    valid_date = coerce_value("01/15/2024", "date")
    invalid_date = coerce_value("not-a-date", "date")
    schema = {"fields": {"signup_date": {"type": "date", "required": True}}}

    assert valid_date == "2024-01-15"
    assert validate_record({"signup_date": valid_date}, schema) == []
    assert invalid_date is None
    assert validate_record({"signup_date": invalid_date}, schema) == ["missing required field 'signup_date'"]


def test_enum_validation_accepts_allowed_value_and_rejects_disallowed_value():
    schema = {"fields": {"status": {"type": "string", "required": True, "enum": ["active", "inactive"]}}}

    assert validate_record({"status": "active"}, schema) == []
    assert validate_record({"status": "pending"}, schema) == [
        "field 'status' value 'pending' not in allowed set ['active', 'inactive']"
    ]
