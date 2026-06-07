import sys
from pathlib import Path

# The repo is currently an uninstalled flat source tree, so keep pytest imports local to the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reconcile_agent.llm import propose_mapping


def test_exact_normalized_match_maps_to_same_field_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    schema = {"fields": {"customer_name": {"type": "string", "required": True}}}
    sample = [{"customer_name": "Jane Doe"}]

    mapping = propose_mapping(sample=sample, target_schema=schema)

    assert mapping == {"customer_name": {"source": "customer_name", "type": "string"}}


def test_supported_synonym_match_maps_using_existing_synonym_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    schema = {"fields": {"full_name": {"type": "string", "required": True}}}
    sample = [{"customername": "Jane Doe"}]

    mapping = propose_mapping(sample=sample, target_schema=schema)

    assert mapping == {"full_name": {"source": "customername", "type": "string"}}


def test_unknown_fields_are_not_hallucinated_into_unrelated_required_targets(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    schema = {"fields": {"email": {"type": "email", "required": True}}}
    sample = [{"favorite_color": "blue", "pet_name": "Milo"}]

    mapping = propose_mapping(sample=sample, target_schema=schema)

    assert mapping == {"email": {"source": None, "type": "email"}}


def test_one_character_source_field_does_not_match_email_by_generic_substring(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    schema = {"fields": {"email": {"type": "email", "required": True}}}
    sample = [{"e": "not actually email", "favorite_color": "blue"}]

    mapping = propose_mapping(sample=sample, target_schema=schema)

    assert mapping == {"email": {"source": None, "type": "email"}}


def test_two_character_source_field_does_not_match_email_by_generic_substring(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    schema = {"fields": {"email": {"type": "email", "required": True}}}
    sample = [{"em": "not actually email", "favorite_color": "blue"}]

    mapping = propose_mapping(sample=sample, target_schema=schema)

    assert mapping == {"email": {"source": None, "type": "email"}}


def test_offline_mode_without_anthropic_api_key_returns_deterministic_mapping(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    schema = {
        "fields": {
            "email": {"type": "email", "required": True},
            "amount": {"type": "number", "required": True},
            "active": {"type": "boolean"},
        }
    }
    sample = [{"contactemail": "jane@example.com", "amt": "$10.00", "enabled": "yes"}]

    first_mapping = propose_mapping(sample=sample, target_schema=schema)
    second_mapping = propose_mapping(sample=sample, target_schema=schema)

    assert first_mapping == {
        "email": {"source": "contactemail", "type": "email"},
        "amount": {"source": "amt", "type": "number"},
        "active": {"source": "enabled", "type": "boolean"},
    }
    assert second_mapping == first_mapping
