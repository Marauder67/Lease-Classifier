"""
Track B — U.S. federal income-tax classification.

True Lease (Tax Lease) vs. Conditional Sale, under the Rev. Proc. 2001-28
20/20/20 safe-harbor guidelines and the Rev. Rul. 55-540 economic-substance
factors, informed by the Frank Lyon substance-over-form doctrine.

A bargain purchase / automatic transfer of ownership is dispositive toward
Conditional Sale regardless of the other factors.
"""

from __future__ import annotations

from app.engine.common import Confidence, Criterion, Result, TaxVerdict, TrackResult
from app.engine.economics import EconomicsResult
from app.engine.thresholds import (
    TAX_MIN_LESSOR_EQUITY,
    TAX_MIN_REMAINING_LIFE,
    TAX_MIN_REMAINING_LIFE_YEARS,
    TAX_MIN_RESIDUAL,
    is_nominal_consideration,
)
from app.models import EndOfTermOption, ExtractedTerms, UserInputs

REGIME = "Tax (IRC)"


def classify_tax(
    terms: ExtractedTerms,
    inputs: UserInputs,
    econ: EconomicsResult,
) -> TrackResult:
    cost = terms.total_equipment_cost
    life = inputs.economic_useful_life_years
    term_years = (terms.lease_term_months / 12) if terms.lease_term_months else None

    nominal, nominal_rationale = is_nominal_consideration(
        terms.end_of_term_option, terms.purchase_option_price,
        inputs.estimated_end_of_term_fmv,
    )
    bargain = bool(nominal) or terms.automatic_ownership_transfer is True

    # Residual that actually belongs to the lessor at end of term.
    if bargain:
        residual_to_lessor = terms.purchase_option_price or 0.0
    else:
        residual_to_lessor = inputs.estimated_end_of_term_fmv

    criteria: list[Criterion] = []

    # Factor 1 — min 20% lessor at-risk equity investment -------------------
    if cost and residual_to_lessor is not None:
        ratio = residual_to_lessor / cost
        res = Result.PASS if (not bargain and ratio >= TAX_MIN_LESSOR_EQUITY) else Result.FAIL
        criteria.append(Criterion(
            1, "Min 20% lessor at-risk equity investment",
            f"Lessor residual position {ratio:.2%} of cost", ">= 20%",
            res, Confidence.HIGH if bargain else Confidence.MEDIUM,
            "No unconditional at-risk equity — full payout with nominal residual." if res == Result.FAIL else ""))
    else:
        criteria.append(_insufficient(1, "Min 20% lessor at-risk equity investment", ">= 20%"))

    # Factor 2 — min 20% residual value to lessor ---------------------------
    if cost and residual_to_lessor is not None:
        ratio = residual_to_lessor / cost
        res = Result.PASS if (not bargain and ratio >= TAX_MIN_RESIDUAL) else Result.FAIL
        criteria.append(Criterion(
            2, "Min 20% residual value at end of term",
            f"Contractual residual to lessor = {_fmt(residual_to_lessor)} ({ratio:.2%})",
            ">= 20% of cost", res, Confidence.HIGH if bargain else Confidence.MEDIUM,
            "Market residual may exceed 20% but does not belong to the lessor." if res == Result.FAIL else ""))
    else:
        criteria.append(_insufficient(2, "Min 20% residual value at end of term", ">= 20% of cost"))

    # Factor 3 — remaining useful life >= 20% of original & >= 1 year --------
    if life and term_years is not None:
        remaining = life - term_years
        ratio = remaining / life
        res = (Result.PASS if (ratio >= TAX_MIN_REMAINING_LIFE and remaining >= TAX_MIN_REMAINING_LIFE_YEARS)
               else Result.FAIL)
        criteria.append(Criterion(
            3, "Remaining useful life >= 20% of original & >= 1 year",
            f"{remaining:.1f} of {life:.1f} yrs remaining = {ratio:.1%}",
            ">= 20% and >= 1 yr", res, Confidence.HIGH, ""))
    else:
        criteria.append(_insufficient(3, "Remaining useful life >= 20% of original & >= 1 year", ">= 20% and >= 1 yr"))

    # Factor 4 — no lessee investment in the equipment ----------------------
    if terms.down_payment is not None:
        res = Result.PASS if terms.down_payment == 0 else Result.FAIL
        criteria.append(Criterion(
            4, "No lessee investment in the equipment",
            f"Down payment {_fmt(terms.down_payment)}", "$0 lessee investment",
            res, Confidence.HIGH, ""))
    else:
        criteria.append(_insufficient(4, "No lessee investment in the equipment", "$0 lessee investment"))

    # Factor 5 — no bargain purchase or bargain renewal ---------------------
    if nominal is True or terms.automatic_ownership_transfer is True:
        criteria.append(Criterion(
            5, "No bargain purchase or bargain renewal",
            "Bargain purchase / automatic transfer present", "No bargain option",
            Result.FAIL, Confidence.HIGH,
            f"{nominal_rationale} Dispositive toward conditional sale."))
    elif nominal is False:
        criteria.append(Criterion(
            5, "No bargain purchase or bargain renewal",
            "FMV / non-nominal purchase option", "No bargain option",
            Result.PASS, Confidence.MEDIUM, nominal_rationale))
    else:
        criteria.append(_insufficient(5, "No bargain purchase or bargain renewal", "No bargain option"))

    # Factor 6 — profit motive independent of tax benefits ------------------
    criteria.append(Criterion(
        6, "Profit motive independent of tax benefits",
        f"Solved implicit yield {econ.solved_implicit_yield:.2%} (lending-spread economics)",
        "Independent profit motive", Result.PASS, Confidence.MEDIUM,
        "Lessor's return resembles a lending spread; consistent with financing rather "
        "than tax-shelter economics."))

    verdict, confidence, extra_notes = _tax_verdict(criteria, bargain)

    citations = [
        {"authority": "Rev. Proc. 2001-28, 2001-1 C.B. 1156",
         "note": "20/20/20 leveraged-lease safe harbor",
         "url": "https://www.irs.gov/pub/irs-drop/rp-01-28.pdf"},
        {"authority": "Rev. Rul. 55-540, 1955-2 C.B. 39",
         "note": "Six-factor lease vs. conditional-sale test", "url": ""},
        {"authority": "Frank Lyon Co. v. United States, 435 U.S. 561 (1978)",
         "note": "Substance-over-form doctrine",
         "url": "https://supreme.justia.com/cases/federal/us/435/561/"},
    ]
    return TrackResult(REGIME, verdict, confidence, criteria, citations, extra_notes)


def _tax_verdict(criteria: list[Criterion], bargain: bool) -> tuple[str, Confidence, list[str]]:
    notes: list[str] = []
    # Dispositive: bargain purchase / automatic transfer -> conditional sale.
    if bargain:
        notes.append(
            "Frank Lyon substance-over-form: with a bargain purchase / automatic transfer "
            "and full-payout economics, the transaction has no independent lease substance. "
            "Lessee claims MACRS depreciation and deducts the interest component of each "
            "payment; it cannot deduct payments as rent. Lessor recognises principal + "
            "interest income and does not claim §168 depreciation.")
        return TaxVerdict.CONDITIONAL_SALE.value, Confidence.HIGH, notes

    results = {c.number: c.result for c in criteria}
    if any(r == Result.INSUFFICIENT for n, r in results.items() if n in (1, 2, 5)):
        return TaxVerdict.INSUFFICIENT.value, Confidence.LOW, notes

    safe_harbor = [1, 2, 3, 4, 5]
    if all(results.get(n) == Result.PASS for n in safe_harbor):
        return TaxVerdict.TRUE_LEASE.value, Confidence.MEDIUM, notes
    # Fails safe harbor without a bargain option -> lean conditional sale on economics.
    return TaxVerdict.CONDITIONAL_SALE.value, Confidence.MEDIUM, notes


def _insufficient(number: int, name: str, threshold: str) -> Criterion:
    return Criterion(number, name, "Required input not supplied", threshold,
                     Result.INSUFFICIENT, Confidence.LOW,
                     "Marked insufficient rather than guessed.")


def _fmt(v: float | None) -> str:
    return "not supplied" if v is None else f"${v:,.2f}"
