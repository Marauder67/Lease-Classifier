"""
Golden regression test: the engine must reproduce the v1.1 Davalor Mold report.

If any verdict here changes, the engine's behaviour has drifted from the
governed reference output and the change must be reviewed deliberately.
"""

import json
from pathlib import Path

import pytest

from app.engine.classifier import classify
from app.models import ClassifyRequest

FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "davalor_2025699.json"


@pytest.fixture(scope="module")
def report():
    data = json.loads(FIXTURE.read_text())
    req = ClassifyRequest.model_validate(data)
    return classify(req.terms, req.user_inputs, date_of_analysis="2026-08-13")


def test_three_verdicts(report):
    verdicts = {r.regime: r.verdict for r in report.executive_summary}
    assert verdicts["GAAP (ASC 842)"] == "Finance Lease"
    assert verdicts["Tax (IRC)"] == "Conditional Sale"
    assert verdicts["UCC (§1-203)"] == "UCC Article 9 Disguised Security Interest"


def test_cross_regime_fully_aligned(report):
    assert "Fully aligned" in report.cross_regime_alignment
    assert "financing" in report.cross_regime_alignment


def test_solved_yield(report):
    assert abs(report.solved_economics.solved_implicit_yield - 0.0817) < 0.0005


def test_gaap_criteria_pattern(report):
    # Criteria 1, 2, 4 pass; 3 fails (close); 5 insufficient.
    by_num = {c.number: c for c in report.gaap.criteria}
    assert by_num[1].result == "Pass"
    assert by_num[2].result == "Pass"
    assert by_num[3].result == "Fail"
    assert by_num[4].result == "Pass"


def test_tax_bargain_is_dispositive(report):
    factor5 = next(c for c in report.tax.criteria if c.number == 5)
    assert factor5.result == "Fail"
    assert report.tax.verdict == "Conditional Sale"


def test_ucc_per_se_condition_four(report):
    cond4 = next(c for c in report.ucc.criteria if c.number == 4)
    assert cond4.result == "Pass"  # $1 nominal ownership option


def test_ucc_cites_controlling_ohio_authority(report):
    cites = " ".join(c.get("citation", "") for c in report.ucc.citations)
    assert "QDS Components" in cites  # controlling Ohio authority from the library


def test_no_restructuring_language(report):
    """Governance guardrail: the report must never suggest restructuring."""
    blob = json.dumps(report.model_dump()).lower()
    for banned in ["we recommend restructuring", "to restructure", "you should restructure",
                   "restructure the lease", "to convert this to an operating lease"]:
        assert banned not in blob


def test_traceability_has_dispositive_row(report):
    assert any(r.dispositive.startswith("Yes") for r in report.traceability_matrix)
