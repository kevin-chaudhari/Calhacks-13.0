"""Offline regression tests for Gemini budget grounding."""
import pytest

from rally import compiler


@pytest.mark.parametrize("phrase,amount", [
    ("with some friends", 200),
    ("with 4 people", 4),
    ("with 4 people", 200),
    ("in 2026", 2026),
    ("under $100", 200),
    ("under $1300", 300),
    ("under $300.50", 300),
    ("under $300.501", 300.50),
    ("for 300 people with a budget of 100", 300),
    ("under $-200", 200),
    ("under $200", -200),
    ("under $200", float("nan")),
    ("under $200", float("inf")),
])
def test_unsupported_budget_becomes_a_question(monkeypatch, phrase, amount):
    def fake_extract(*args, **kwargs):
        return compiler.Extracted(
            template_id="trip_activity", activity="scuba_diving",
            budget_amount=amount, budget_currency="USD", budget_per="person",
        )

    monkeypatch.setattr(compiler, "extract_gemini", fake_extract)
    result = compiler.compile_goal(
        "Scuba diving " + phrase, "2026-10-24", "gemini",
        api_key="fake-key", model="fake-model",
    )
    assert result.compiled_by == "gemini"
    assert result.draft.budget_max is None
    assert "budgetMax" in {field.field for field in result.draft.missing}
    assert not any(c.key == "price_per_person" for c in result.draft.conditions)
    assert "Unverified budget omitted; please confirm the amount." in result.warnings


@pytest.mark.parametrize("phrase,amount", [
    ("under $300", 300),
    ("under $300.50", 300.50),
    ("under $1,200.50", 1200.50),
    ("under USD 300", 300),
    ("under USD300", 300),
    ("under US$300", 300),
    ("under 300 USD", 300),
    ("under 300 dollars", 300),
    ("with a budget of 300", 300),
    ("budget: 300", 300),
    ("under $300.", 300),
])
def test_supported_budget_is_preserved(monkeypatch, phrase, amount):
    def fake_extract(*args, **kwargs):
        return compiler.Extracted(
            template_id="trip_activity", activity="scuba_diving",
            budget_amount=amount, budget_currency="USD", budget_per="person",
        )

    monkeypatch.setattr(compiler, "extract_gemini", fake_extract)
    result = compiler.compile_goal(
        "Scuba diving " + phrase, "2026-10-24", "gemini",
        api_key="fake-key", model="fake-model",
    )
    assert result.compiled_by == "gemini"
    assert result.draft.budget_max.amount == amount
    assert "budgetMax" not in {field.field for field in result.draft.missing}
    assert result.warnings == []


def test_missing_budget_stays_missing(monkeypatch):
    monkeypatch.setattr(compiler, "extract_gemini", lambda *a, **k: compiler.Extracted(
        template_id="trip_activity", activity="scuba_diving",
    ))
    result = compiler.compile_goal(
        "Scuba diving", "2026-10-24", "gemini", api_key="fake-key", model="fake-model",
    )
    assert result.draft.budget_max is None
    assert "budgetMax" in {field.field for field in result.draft.missing}
    assert result.warnings == []
