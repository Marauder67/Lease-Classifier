"""Case-law lookup + governance-guardrail tests."""

import pytest

from app.engine import case_law
from app.engine.classifier import classify
from app.models import ClassifyRequest, ExtractedTerms, UserInputs


def test_ohio_returns_controlling_qds():
    cites = case_law.citations_for_state("Ohio")
    assert cites["circuit"] == "Sixth Circuit"
    assert any("QDS Components" in c["citation"] for c in cites["controlling"])
    assert not cites["gap"]


def test_delaware_maps_to_third_circuit_pillowtex():
    cites = case_law.citations_for_state("DE")
    assert cites["circuit"] == "Third Circuit"
    assert any("Pillowtex" in c["citation"] for c in cites["controlling"])


def test_unknown_state_flags_gap_not_invention():
    cites = case_law.citations_for_state("Atlantis")
    assert cites["gap"] is True
    assert cites["controlling"] == []           # never invents a citation
    assert cites["cross_cutting"]               # still returns statutory anchor


def test_missing_core_economics_raises():
    terms = ExtractedTerms(payment_amount=None, total_equipment_cost=None, lease_term_months=None)
    with pytest.raises(ValueError):
        classify(terms, UserInputs())


def test_insufficient_data_is_a_valid_verdict():
    # Enough to solve economics, but no useful life / FMV -> some criteria insufficient.
    terms = ExtractedTerms(
        total_equipment_cost=100000.0, payment_amount=2000.0, lease_term_months=48,
        payment_timing="advance", end_of_term_option="fmv",
        non_cancellable=True, governing_law_state="Ohio",
    )
    report = classify(terms, UserInputs())
    results = {c.number: c.result for c in report.gaap.criteria}
    assert "Insufficient data" in results.values()
