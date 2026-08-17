"""
Bright-line and nominal-consideration thresholds shared across tracks.

These encode the numeric conventions the governed prompt and case-law library
rely on. They are intentionally centralised so a single edit changes the whole
tool's behaviour and so the values are easy to audit.
"""

from __future__ import annotations

from app.models import EndOfTermOption

# ASC 842 practical thresholds
GAAP_LIFE_THRESHOLD = 0.75          # "major part of remaining economic life"
GAAP_PV_THRESHOLD = 0.90            # "substantially all of the fair value"

# Rev. Proc. 2001-28 safe-harbor thresholds
TAX_MIN_LESSOR_EQUITY = 0.20        # >= 20% at-risk equity
TAX_MIN_RESIDUAL = 0.20            # >= 20% residual value to lessor
TAX_MIN_REMAINING_LIFE = 0.20       # >= 20% of original life remaining
TAX_MIN_REMAINING_LIFE_YEARS = 1.0  # and at least one year

# Nominal-consideration bands (UCC §1-203 case law)
NOMINAL_UPPER_BAND = 0.10           # <= 10% of end FMV: nominal unless FMV-tied
NOT_NOMINAL_BAND = 0.25             # >= 25% of end FMV: not nominal


def is_nominal_consideration(
    option_type: EndOfTermOption | None,
    price: float | None,
    end_of_term_fmv: float | None,
) -> tuple[bool | None, str]:
    """Return (is_nominal, rationale).

    is_nominal is True / False / None (None = cannot determine).
    Mirrors the Case Law Library's "Nominal-consideration thresholds" section.
    """
    if option_type == EndOfTermOption.DOLLAR_BUYOUT or (price is not None and price <= 1.0):
        return True, "$1.00 / nominal fixed price — universally treated as nominal."

    if option_type == EndOfTermOption.FMV:
        return False, "Fair-market-value purchase — expressly not nominal (§1-203(c)(6))."

    if price is None or end_of_term_fmv in (None, 0):
        return None, "Cannot determine: purchase price or end-of-term FMV not supplied."

    ratio = price / end_of_term_fmv
    if ratio <= NOMINAL_UPPER_BAND:
        return True, (
            f"Purchase price is {ratio:.1%} of end-of-term FMV (<= 10%); "
            "treated as nominal unless expressly tied to FMV expectation."
        )
    if ratio >= NOT_NOMINAL_BAND:
        return False, (
            f"Purchase price is {ratio:.1%} of end-of-term FMV (>= 25%); not nominal."
        )
    return None, (
        f"Purchase price is {ratio:.1%} of end-of-term FMV (between 10% and 25%); "
        "close call — requires judgment."
    )
