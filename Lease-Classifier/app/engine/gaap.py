"""
Track A — GAAP classification under ASC 842.

Applies the five classification criteria. If ANY one is met, the lease is a
Finance Lease; otherwise it is an Operating Lease. "Insufficient data" is a
valid outcome for any criterion whose inputs are missing.

Cite: ASC 842-10-25-2 (finance-lease classification criteria).
"""

from __future__ import annotations

from app.engine.common import Confidence, Criterion, GaapVerdict, Result, TrackResult
from app.engine.economics import EconomicsResult, present_value
from app.engine.thresholds import (
    GAAP_LIFE_THRESHOLD,
    GAAP_PV_THRESHOLD,
    is_nominal_consideration,
)
from app.models import EndOfTermOption, ExtractedTerms, UserInputs

REGIME = "GAAP (ASC 842)"


def classify_gaap(
    terms: ExtractedTerms,
    inputs: UserInputs,
    econ: EconomicsResult,
) -> TrackResult:
    fmv = inputs.fair_market_value_at_inception or terms.total_equipment_cost
    life = inputs.economic_useful_life_years
    discount_rate = inputs.discount_rate_for_pv_test or econ.solved_implicit_yield
    criteria: list[Criterion] = []

    # --- Criterion 1: transfer of ownership by end of term -------------------
    if terms.automatic_ownership_transfer is True:
        c1 = Criterion(1, "Transfer of ownership by end of term",
                       "Title passes automatically at end of term", "Any automatic transfer",
                       Result.PASS, Confidence.HIGH,
                       "Lease provides for automatic transfer of title — not merely an option.")
    elif terms.automatic_ownership_transfer is False:
        c1 = Criterion(1, "Transfer of ownership by end of term",
                       "No automatic transfer", "Any automatic transfer",
                       Result.FAIL, Confidence.HIGH, "")
    else:
        c1 = Criterion(1, "Transfer of ownership by end of term",
                       "Not stated", "Any automatic transfer",
                       Result.INSUFFICIENT, Confidence.LOW,
                       "Document does not state whether ownership transfers automatically.")
    criteria.append(c1)

    # --- Criterion 2: purchase option reasonably certain to be exercised -----
    nominal, rationale = is_nominal_consideration(
        terms.end_of_term_option, terms.purchase_option_price,
        inputs.estimated_end_of_term_fmv,
    )
    if nominal is True:
        c2 = Criterion(2, "Purchase option reasonably certain to be exercised",
                       f"Purchase price {_fmt_price(terms.purchase_option_price)}",
                       "Reasonably certain", Result.PASS, Confidence.HIGH,
                       "Bargain purchase — economic rationality makes exercise reasonably "
                       f"certain. {rationale}")
    elif nominal is False:
        c2 = Criterion(2, "Purchase option reasonably certain to be exercised",
                       f"Purchase price {_fmt_price(terms.purchase_option_price)}",
                       "Reasonably certain", Result.FAIL, Confidence.MEDIUM, rationale)
    else:
        c2 = Criterion(2, "Purchase option reasonably certain to be exercised",
                       f"Purchase price {_fmt_price(terms.purchase_option_price)}",
                       "Reasonably certain", Result.INSUFFICIENT, Confidence.LOW, rationale)
    criteria.append(c2)

    # --- Criterion 3: term >= major part of remaining economic life ----------
    if terms.lease_term_months and life:
        ratio = (terms.lease_term_months / 12) / life
        res = Result.PASS if ratio >= GAAP_LIFE_THRESHOLD else Result.FAIL
        close = abs(ratio - GAAP_LIFE_THRESHOLD) <= 0.05
        c3 = Criterion(3, "Term >= major part of remaining economic life",
                       f"{terms.lease_term_months} mo / {life*12:.0f} mo = {ratio:.2%}",
                       f"{GAAP_LIFE_THRESHOLD:.0%} practical threshold",
                       res, Confidence.MEDIUM if close else Confidence.HIGH,
                       "Close call." if close else "")
    else:
        c3 = Criterion(3, "Term >= major part of remaining economic life",
                       "Economic useful life not supplied", f"{GAAP_LIFE_THRESHOLD:.0%}",
                       Result.INSUFFICIENT, Confidence.LOW,
                       "Requires user-supplied estimated economic useful life.")
    criteria.append(c3)

    # --- Criterion 4: PV of payments (+ guaranteed residual) >= ~90% FMV -----
    if terms.payment_amount and terms.lease_term_months and fmv:
        buyout = _reasonably_certain_buyout(terms, nominal)
        pv = present_value(
            terms.payment_amount, terms.lease_term_months, discount_rate,
            timing=(terms.payment_timing.value if terms.payment_timing else "advance"),
            buyout=buyout,
        )
        pct = pv / fmv
        res = Result.PASS if pct >= GAAP_PV_THRESHOLD else Result.FAIL
        c4 = Criterion(4, "PV of lease payments >= substantially all of fair value",
                       f"PV @ {discount_rate:.2%} = {pct:.2%} of fair value",
                       f"{GAAP_PV_THRESHOLD:.0%} practical threshold",
                       res, Confidence.HIGH,
                       "Uses solved implicit yield by default." )
    else:
        c4 = Criterion(4, "PV of lease payments >= substantially all of fair value",
                       "Payment, term, or fair value not supplied",
                       f"{GAAP_PV_THRESHOLD:.0%}", Result.INSUFFICIENT, Confidence.LOW, "")
    criteria.append(c4)

    # --- Criterion 5: specialized asset with no alternative use --------------
    c5 = Criterion(5, "Specialized asset with no alternative use to lessor",
                   "Requires judgment / not supplied", "Specialized, no alternative use",
                   Result.INSUFFICIENT, Confidence.LOW,
                   "Not determinable from the document; not outcome-determinative when "
                   "Criteria 1, 2, or 4 already trigger a finance lease.")
    criteria.append(c5)

    verdict, confidence = _gaap_verdict(criteria)
    notes = []
    if verdict == GaapVerdict.FINANCE.value:
        fw = "public" if (inputs.reporting_framework and inputs.reporting_framework.value == "public") else "private"
        notes.append(
            "Accounting consequence: recognise a right-of-use asset and lease liability "
            "at the present value of remaining payments; recognise interest and "
            f"amortisation separately (front-loaded), not straight-line lease expense "
            f"({fw}-company reporting under ASC 842). Cite: ASC 842-10-25-2.")

    return TrackResult(
        regime=REGIME, verdict=verdict, confidence=confidence,
        criteria=criteria,
        citations=[{"authority": "FASB ASC 842-10-25-2",
                    "note": "Finance-lease classification criteria",
                    "url": "https://asc.fasb.org/842"}],
        notes=notes,
    )


def _reasonably_certain_buyout(terms: ExtractedTerms, nominal: bool | None) -> float:
    """Include the purchase-option payment in the PV when exercise is reasonably
    certain (a bargain purchase) — consistent with ASC 842 lease-payment scope."""
    if nominal is True and terms.purchase_option_price is not None:
        return terms.purchase_option_price
    if terms.end_of_term_option == EndOfTermOption.DOLLAR_BUYOUT:
        return terms.purchase_option_price or 1.0
    return 0.0


def _gaap_verdict(criteria: list[Criterion]) -> tuple[str, Confidence]:
    passes = [c for c in criteria if c.result == Result.PASS]
    if passes:
        conf = Confidence.HIGH if any(c.confidence == Confidence.HIGH for c in passes) else Confidence.MEDIUM
        return GaapVerdict.FINANCE.value, conf
    # No passes. If a criterion that *could* pass is insufficient, we can't be sure.
    flippable = {1, 2, 4}  # criteria whose PASS forces finance lease
    if any(c.result == Result.INSUFFICIENT and c.number in flippable for c in criteria):
        return GaapVerdict.INSUFFICIENT.value, Confidence.LOW
    return GaapVerdict.OPERATING.value, Confidence.MEDIUM


def _fmt_price(price: float | None) -> str:
    if price is None:
        return "not stated"
    return f"${price:,.2f}"
