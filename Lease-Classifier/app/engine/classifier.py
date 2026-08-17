"""
Orchestrator — runs the three independent tracks and assembles the governed
report. This is the single entry point the API and tests call.

Governance guarantees enforced here:
  * The three regimes are always computed and reported separately.
  * All economics come from the deterministic solver, never an LLM.
  * "Insufficient data" propagates instead of being guessed away.
  * No restructuring advice is ever generated (see governance_notes).
"""

from __future__ import annotations

from app.engine import case_law
from app.engine.common import Confidence, Result
from app.engine.economics import compute_economics
from app.engine.gaap import classify_gaap
from app.engine.tax import classify_tax
from app.engine.thresholds import is_nominal_consideration
from app.engine.ucc import classify_ucc
from app.models import (
    ClassificationReport,
    CriterionOut,
    EndOfTermOption,
    ExecutiveSummaryRow,
    ExtractedTerms,
    SolvedEconomicsOut,
    TraceabilityRow,
    TrackOut,
    UserInputs,
)

GOVERNANCE_NOTES = [
    "No restructuring suggestions were provided.",
    "No legal or tax opinion is rendered — this is a diagnostic classification only.",
    "The three regimes were analysed independently.",
    "Case-law citations are drawn only from the controlled EFG Case Law Library; no invented citations.",
    "Any input that could not be determined is marked 'Insufficient data' rather than guessed.",
]


def classify(terms: ExtractedTerms, inputs: UserInputs, *, date_of_analysis: str | None = None) -> ClassificationReport:
    _require_economics_inputs(terms)

    # ---- Solve economics ---------------------------------------------------
    buyout, residual = _economic_tail(terms, inputs)
    extra_rates: dict[str, float] = {}
    if inputs.discount_rate_for_pv_test:
        extra_rates["user_discount_rate"] = inputs.discount_rate_for_pv_test
    econ = compute_economics(
        terms.total_equipment_cost, terms.payment_amount, terms.lease_term_months,
        timing=(terms.payment_timing.value if terms.payment_timing else "advance"),
        buyout=buyout, residual=residual,
        stated_index_rate=terms.stated_index_rate, extra_rates=extra_rates,
    )

    # ---- Run the three tracks ---------------------------------------------
    gaap = classify_gaap(terms, inputs, econ)
    tax = classify_tax(terms, inputs, econ)
    ucc = classify_ucc(terms, inputs, econ)

    # ---- Assemble report ---------------------------------------------------
    summary = [
        ExecutiveSummaryRow(regime=gaap.regime, verdict=gaap.verdict, confidence=gaap.confidence.value),
        ExecutiveSummaryRow(regime=tax.regime, verdict=tax.verdict, confidence=tax.confidence.value),
        ExecutiveSummaryRow(regime=ucc.regime, verdict=ucc.verdict, confidence=ucc.confidence.value),
    ]
    alignment = _cross_regime_alignment(gaap.verdict, tax.verdict, ucc.verdict)

    econ_out = SolvedEconomicsOut(
        stated_index_rate=terms.stated_index_rate,
        solved_implicit_yield=econ.solved_implicit_yield,
        undiscounted_total_payments=econ.undiscounted_total_payments,
        pv_percent_at_rate={k: round(v, 2) for k, v in econ.pv_percent_at_rate.items()},
        notes=_economics_notes(terms, econ),
    )

    report = ClassificationReport(
        document=terms.document_name,
        lessee=terms.lessee,
        lessor=terms.lessor,
        lease_date_term_cost=_lease_headline(terms),
        governing_law=terms.governing_law_state,
        date_of_analysis=date_of_analysis,
        executive_summary=summary,
        cross_regime_alignment=alignment,
        extracted_terms=terms,
        user_inputs=inputs,
        solved_economics=econ_out,
        traceability_matrix=_traceability(terms, inputs, econ),
        gaap=_to_out(gaap),
        tax=_to_out(tax),
        ucc=_to_out(ucc),
        flagged_ambiguities=_flagged_ambiguities(gaap, tax, ucc),
        authorities_cited=_authorities(gaap, tax, ucc),
        governance_notes=GOVERNANCE_NOTES,
    )
    return report


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _require_economics_inputs(terms: ExtractedTerms) -> None:
    missing = [name for name, val in {
        "total_equipment_cost": terms.total_equipment_cost,
        "payment_amount": terms.payment_amount,
        "lease_term_months": terms.lease_term_months,
    }.items() if not val]
    if missing:
        raise ValueError(
            "Cannot run classification without core economics. Missing: "
            + ", ".join(missing)
            + ". Collect these in the missing-input interview before classifying.")


def _economic_tail(terms: ExtractedTerms, inputs: UserInputs) -> tuple[float, float]:
    """Contractual end-of-term amounts assured to the lessor, for the solver."""
    if terms.end_of_term_option == EndOfTermOption.FMV:
        return 0.0, (inputs.estimated_end_of_term_fmv or 0.0)
    return (terms.purchase_option_price or 0.0), 0.0


def _cross_regime_alignment(gaap: str, tax: str, ucc: str) -> str:
    financing_like = {
        "Finance Lease", "Conditional Sale", "UCC Article 9 Disguised Security Interest",
    }
    true_lease_like = {
        "Operating Lease", "True Lease (Tax Lease)", "UCC Article 2A True Lease",
    }
    verdicts = [gaap, tax, ucc]
    if "Insufficient data" in verdicts:
        return "Partial — one or more regimes returned Insufficient data; see tracks."
    if all(v in financing_like for v in verdicts):
        return "Fully aligned — all three regimes recharacterize as financing."
    if all(v in true_lease_like for v in verdicts):
        return "Fully aligned — all three regimes treat this as a true lease."
    return "Split — regimes diverge; see each track."


def _economics_notes(terms: ExtractedTerms, econ) -> list[str]:
    notes = []
    if terms.stated_index_rate is not None:
        notes.append(
            f"Stated index rate ({terms.stated_index_rate:.2%}) is typically only a "
            f"component of pricing; the solved implicit yield ({econ.solved_implicit_yield:.2%}) "
            "is the true yield to lessor and is used as the default PV-test rate.")
    return notes


def _lease_headline(terms: ExtractedTerms) -> str:
    parts = []
    if terms.lease_term_months:
        parts.append(f"{terms.lease_term_months} months")
    if terms.payment_amount:
        timing = terms.payment_timing.value if terms.payment_timing else ""
        parts.append(f"${terms.payment_amount:,.2f}/payment {timing}".strip())
    if terms.total_equipment_cost:
        parts.append(f"cost ${terms.total_equipment_cost:,.2f}")
    if terms.purchase_option_price is not None:
        parts.append(f"${terms.purchase_option_price:,.2f} end-of-term option")
    return " · ".join(parts)


def _to_out(track) -> TrackOut:
    return TrackOut(
        regime=track.regime, verdict=track.verdict, confidence=track.confidence.value,
        criteria=[CriterionOut(**c.as_dict()) for c in track.criteria],
        citations=track.citations, notes=track.notes,
    )


def _flagged_ambiguities(*tracks) -> list[str]:
    flags = []
    for t in tracks:
        for c in t.criteria:
            if c.result == Result.INSUFFICIENT:
                flags.append(f"{t.regime} — Criterion {c.number} ({c.name}): {c.input_value}.")
            elif c.confidence == Confidence.MEDIUM and "close" in (c.analysis or "").lower():
                flags.append(f"{t.regime} — Criterion {c.number} ({c.name}): close call, {c.input_value}.")
    return flags


def _authorities(*tracks) -> list[str]:
    seen, out = set(), []
    for t in tracks:
        for c in t.citations:
            key = c.get("authority") or c.get("citation")
            if key and key not in seen:
                seen.add(key)
                url = c.get("url")
                out.append(f"{key}" + (f" — {url}" if url else ""))
    return out


def _traceability(terms: ExtractedTerms, inputs: UserInputs, econ) -> list[TraceabilityRow]:
    rows: list[TraceabilityRow] = []
    nominal, _ = is_nominal_consideration(
        terms.end_of_term_option, terms.purchase_option_price, inputs.estimated_end_of_term_fmv)
    bargain = bool(nominal) or terms.automatic_ownership_transfer is True

    if bargain:
        rows.append(TraceabilityRow(
            fact="Bargain purchase / automatic ownership transfer",
            gaap_triggered="Criteria 1 & 2 (either alone triggers Finance Lease)",
            tax_triggered="Rev. Proc. 2001-28 factors 1, 2, 5",
            ucc_triggered="§1-203(b)(4) per se (nominal-consideration ownership option)",
            dispositive="Yes — single-fact dispositive across all three regimes"))
    if terms.non_cancellable:
        rows.append(TraceabilityRow(
            fact="Non-cancellability by lessee",
            gaap_triggered="Reinforces Criterion 4 (payment obligation fixed)",
            tax_triggered="Reinforces factor 1",
            ucc_triggered="§1-203(b) precondition (required for per se)",
            dispositive="Required precondition for UCC per se"))
    pv_pct = econ.pv_percent_at_rate.get("solved_implicit")
    if pv_pct is not None:
        rows.append(TraceabilityRow(
            fact=f"PV of payments ~ {pv_pct:.0f}% of cost (solved implicit rate)",
            gaap_triggered="Criterion 4 (90% threshold)",
            tax_triggered="Reinforces factor 1 (full principal recovery)",
            ucc_triggered="Economic-realities factor (Pillowtex)",
            dispositive="Contributory"))
    if terms.lease_term_months and inputs.economic_useful_life_years:
        ratio = (terms.lease_term_months / 12) / inputs.economic_useful_life_years
        rows.append(TraceabilityRow(
            fact=f"Term vs. economic life ({ratio:.1%})",
            gaap_triggered="Criterion 3",
            tax_triggered="Factor 3 (remaining-life test)",
            ucc_triggered="§1-203(b)(1)",
            dispositive="Non-dispositive"))
    if terms.hell_or_high_water:
        rows.append(TraceabilityRow(
            fact="Hell-or-high-water clause",
            gaap_triggered="Supporting", tax_triggered="Supporting",
            ucc_triggered="Supporting economic-realities factor", dispositive="Contributory"))
    if terms.lessee_state_of_organization:
        rows.append(TraceabilityRow(
            fact=f"Lessee organised in {terms.lessee_state_of_organization}",
            ucc_triggered="Determines UCC-1 filing office (debtor location, §9-307)",
            dispositive="Perfection mechanics, not classification"))
    return rows
