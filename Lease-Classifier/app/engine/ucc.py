"""
Track C — UCC §1-203 classification (Article 2A true lease vs. Article 9
disguised security interest).

Two-step test, applied without presumption:
  1. Per se bright-line test (§1-203(b)): a security interest exists if the
     lessee's obligation is not subject to termination AND any one of four
     conditions is met.
  2. Economic-realities test (§1-203(a)/(c)-(e)): only reached if the per se
     test is not satisfied; asks whether the lessor retained a meaningful
     reversionary interest.

Case citations are drawn only from the controlled Case Law Library.
"""

from __future__ import annotations

from app.engine import case_law
from app.engine.common import Confidence, Criterion, Result, TrackResult, UccVerdict
from app.engine.economics import EconomicsResult
from app.engine.thresholds import is_nominal_consideration
from app.models import ExtractedTerms, UserInputs

REGIME = "UCC (§1-203)"


def classify_ucc(
    terms: ExtractedTerms,
    inputs: UserInputs,
    econ: EconomicsResult,
) -> TrackResult:
    life = inputs.economic_useful_life_years
    term_years = (terms.lease_term_months / 12) if terms.lease_term_months else None
    nominal, nominal_rationale = is_nominal_consideration(
        terms.end_of_term_option, terms.purchase_option_price,
        inputs.estimated_end_of_term_fmv,
    )

    conditions: list[Criterion] = []

    # Precondition — non-terminability by the lessee.
    precondition_met = terms.non_cancellable is True
    if terms.non_cancellable is None:
        precondition_state = Result.INSUFFICIENT
    else:
        precondition_state = Result.PASS if precondition_met else Result.FAIL
    conditions.append(Criterion(
        0, "Precondition: lessee's obligation not subject to termination",
        "Non-cancellable by lessee" if precondition_met else
        ("Cancellable / not stated" if not precondition_met else ""),
        "Required for per se test",
        precondition_state,
        Confidence.HIGH if terms.non_cancellable is not None else Confidence.LOW,
        "Hell-or-high-water / non-cancellation clause." if precondition_met else ""))

    # Condition 1 — term >= remaining economic life.
    if term_years is not None and life:
        ratio = term_years / life
        conditions.append(Criterion(
            1, "Term >= remaining economic life",
            f"{term_years:.2f} / {life:.2f} yrs = {ratio:.1%}", ">= 100%",
            Result.PASS if ratio >= 1.0 else Result.FAIL, Confidence.HIGH, ""))
    else:
        conditions.append(_insufficient(1, "Term >= remaining economic life", ">= 100%"))

    # Condition 2 — lessee bound to renew for remaining life or become owner.
    becomes_owner = terms.automatic_ownership_transfer is True
    conditions.append(Criterion(
        2, "Lessee bound to renew for remaining life or become owner",
        "Automatic ownership transfer" if becomes_owner else "No such obligation",
        "Bound to own/renew",
        Result.PASS if becomes_owner else Result.FAIL, Confidence.HIGH, ""))

    # Condition 3 — renewal option for remaining life at no/nominal consideration.
    conditions.append(Criterion(
        3, "Renewal for remaining life at no/nominal consideration",
        "No such renewal option", "Nominal renewal",
        Result.FAIL, Confidence.MEDIUM, ""))

    # Condition 4 — ownership option for no/nominal consideration.
    if nominal is True:
        conditions.append(Criterion(
            4, "Ownership option at no/nominal consideration",
            f"Purchase price {_fmt(terms.purchase_option_price)}", "Nominal consideration",
            Result.PASS, Confidence.HIGH,
            f"{nominal_rationale} Paradigm case under §1-203(b)(4)."))
    elif nominal is False:
        conditions.append(Criterion(
            4, "Ownership option at no/nominal consideration",
            f"Purchase price {_fmt(terms.purchase_option_price)}", "Nominal consideration",
            Result.FAIL, Confidence.MEDIUM, nominal_rationale))
    else:
        conditions.append(_insufficient(4, "Ownership option at no/nominal consideration", "Nominal consideration"))

    # --- Resolve per se test ------------------------------------------------
    numbered = [c for c in conditions if c.number in (1, 2, 3, 4)]
    any_condition = any(c.result == Result.PASS for c in numbered)
    per_se_met = precondition_met and any_condition

    cites = case_law.citations_for_state(terms.governing_law_state)
    citations = _format_citations(cites)
    notes: list[str] = []
    if cites["gap"]:
        notes.append("LIBRARY GAP: " + cites["gap_note"])

    if per_se_met:
        verdict = UccVerdict.SECURITY_INTEREST.value
        confidence = Confidence.HIGH
        trigger = next(c for c in numbered if c.result == Result.PASS)
        notes.append(
            f"Per se security interest as a matter of law (§1-203(b)) — precondition met "
            f"and condition {trigger.number} satisfied. Economic-realities analysis not "
            "required. Article 2A does not apply.")
    elif precondition_state == Result.INSUFFICIENT or _has_insufficient(numbered):
        verdict, confidence = _economic_realities(terms, inputs, econ, conditions, notes, allow_insufficient=True)
    else:
        # Survives per se -> economic-realities test.
        verdict, confidence = _economic_realities(terms, inputs, econ, conditions, notes, allow_insufficient=False)

    return TrackResult(REGIME, verdict, confidence, conditions, citations, notes)


def _economic_realities(terms, inputs, econ, conditions, notes, allow_insufficient):
    """Second-step test: did the lessor retain a meaningful reversionary interest?"""
    cost = terms.total_equipment_cost
    pv_pct = econ.pv_percent_at_rate.get("solved_implicit")
    end_fmv = inputs.estimated_end_of_term_fmv
    meaningful_residual = None
    if cost and end_fmv is not None:
        meaningful_residual = (end_fmv / cost) >= 0.20

    conditions.append(Criterion(
        99, "Economic realities: lessor's meaningful reversionary interest",
        (f"PV of rents ~ {pv_pct:.1f}% of cost; " if pv_pct else "") +
        (f"end-of-term FMV {end_fmv/cost:.1%} of cost" if (cost and end_fmv is not None) else "residual not supplied"),
        "Lessor retains meaningful reversionary interest",
        Result.FAIL if meaningful_residual is False else (Result.PASS if meaningful_residual else Result.INSUFFICIENT),
        Confidence.MEDIUM if meaningful_residual is not None else Confidence.LOW,
        "Framework per In re Pillowtex / In re WorldCom: nominal option, PV of rents >= cost, "
        "term covers useful life."))

    if pv_pct is not None and pv_pct >= 100.0 and meaningful_residual is False:
        notes.append("Economic realities independently support Article 9: PV of rents >= cost "
                     "and lessor bears no meaningful residual risk.")
        return UccVerdict.SECURITY_INTEREST.value, Confidence.MEDIUM
    if meaningful_residual is True:
        return UccVerdict.TRUE_LEASE.value, Confidence.MEDIUM
    if allow_insufficient:
        return UccVerdict.INSUFFICIENT.value, Confidence.LOW
    return UccVerdict.TRUE_LEASE.value, Confidence.LOW


def _format_citations(cites: dict) -> list[dict]:
    out: list[dict] = []
    for c in cites.get("controlling", []):
        out.append({**c, "weight": "controlling", "circuit": cites.get("circuit")})
    for c in cites.get("persuasive", []):
        out.append({**c, "weight": "persuasive", "circuit": cites.get("circuit")})
    for c in cites.get("cross_cutting", []):
        out.append({**c, "weight": "cross-cutting"})
    return out


def _has_insufficient(cs) -> bool:
    return any(c.result == Result.INSUFFICIENT for c in cs)


def _insufficient(number: int, name: str, threshold: str) -> Criterion:
    return Criterion(number, name, "Required input not supplied", threshold,
                     Result.INSUFFICIENT, Confidence.LOW, "Marked insufficient rather than guessed.")


def _fmt(v: float | None) -> str:
    return "not supplied" if v is None else f"${v:,.2f}"
