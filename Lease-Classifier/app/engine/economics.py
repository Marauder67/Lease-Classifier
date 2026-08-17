"""
Deterministic lease economics.

Nothing in this module is ever produced by a language model. Every number the
classifier relies on — the implicit yield to lessor, present-value percentages,
useful-life ratios — is computed here in plain Python so it is reproducible and
auditable. This is the single most important governance property of the tool.

Public functions
----------------
present_value(...)        -> PV of a payment stream (+ buyout + residual)
solve_implicit_rate(...)  -> the annual yield that makes PV == equipment cost
pv_percent_of_cost(...)   -> PV expressed as a % of a reference value
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EconomicsResult:
    """Everything the three tracks need from the cash-flow math."""

    stated_index_rate: float | None          # e.g. 0.0397 (SOFR index), if in the doc
    solved_implicit_yield: float             # annual, e.g. 0.0817
    periods_per_year: int
    undiscounted_total_payments: float
    # PV of (payments + buyout + guaranteed residual), keyed by the annual rate used
    pv_at_rate: dict[str, float]
    pv_percent_at_rate: dict[str, float]     # same, expressed as % of equipment cost


def present_value(
    payment: float,
    n_periods: int,
    annual_rate: float,
    *,
    timing: str = "advance",
    buyout: float = 0.0,
    residual: float = 0.0,
    periods_per_year: int = 12,
) -> float:
    """Present value of a level payment stream plus end-of-term amounts.

    timing = "advance" (annuity-due, payment at start of period) or
             "arrears" (ordinary annuity, payment at end of period).
    buyout   = purchase-option payment made at end of term (e.g. $1).
    residual = expected residual value the lessor recovers at end of term.
    """
    if n_periods <= 0:
        raise ValueError("n_periods must be positive")

    r = annual_rate / periods_per_year

    if r == 0:
        annuity = payment * n_periods
        tail = buyout + residual
    else:
        # PV of an ordinary annuity of `payment` for n periods
        annuity = payment * (1 - (1 + r) ** -n_periods) / r
        if timing == "advance":
            annuity *= (1 + r)  # shift each payment one period earlier
        tail = (buyout + residual) * (1 + r) ** -n_periods

    return annuity + tail


def solve_implicit_rate(
    equipment_cost: float,
    payment: float,
    n_periods: int,
    *,
    timing: str = "advance",
    buyout: float = 0.0,
    residual: float = 0.0,
    periods_per_year: int = 12,
) -> float:
    """Solve for the annual implicit yield to lessor.

    Returns the annual rate r such that:
        PV(payments + buyout + residual, r) == equipment_cost

    Uses bisection on the monthly rate — robust and deterministic (no reliance
    on a good starting guess the way Newton-Raphson needs). Bracket is wide
    enough for any realistic equipment-finance transaction (0% to ~180% APR).
    """
    def pv_minus_cost(annual: float) -> float:
        return (
            present_value(
                payment,
                n_periods,
                annual,
                timing=timing,
                buyout=buyout,
                residual=residual,
                periods_per_year=periods_per_year,
            )
            - equipment_cost
        )

    lo, hi = 0.0, 15.0  # annual rate bracket: 0% .. 1500%
    f_lo = pv_minus_cost(lo)
    f_hi = pv_minus_cost(hi)
    if f_lo * f_hi > 0:
        # No sign change in bracket — cannot solve (e.g. payments never amortize).
        raise ValueError(
            "Cannot solve implicit rate: PV does not cross equipment cost in bracket. "
            "Check payment, term, and cost inputs."
        )

    for _ in range(200):  # ~2^-200 precision; converges in <60 in practice
        mid = (lo + hi) / 2
        f_mid = pv_minus_cost(mid)
        # PV decreases as rate increases, so pick the half that still brackets zero
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid
    return (lo + hi) / 2


def compute_economics(
    equipment_cost: float,
    payment: float,
    n_periods: int,
    *,
    timing: str = "advance",
    buyout: float = 0.0,
    residual: float = 0.0,
    stated_index_rate: float | None = None,
    extra_rates: dict[str, float] | None = None,
    periods_per_year: int = 12,
) -> EconomicsResult:
    """Run the full economics pass used by the report.

    `extra_rates` lets the caller add named comparison rates (e.g. an IBR the
    user supplied, or the stated index) so the report can show PV at each rate
    the way the governed report format does.
    """
    solved = solve_implicit_rate(
        equipment_cost, payment, n_periods,
        timing=timing, buyout=buyout, residual=residual,
        periods_per_year=periods_per_year,
    )

    rates: dict[str, float] = {"solved_implicit": solved}
    if stated_index_rate is not None:
        rates["stated_index"] = stated_index_rate
    if extra_rates:
        rates.update(extra_rates)

    pv_at_rate: dict[str, float] = {}
    pv_percent_at_rate: dict[str, float] = {}
    for label, rate in rates.items():
        pv = present_value(
            payment, n_periods, rate,
            timing=timing, buyout=buyout, residual=residual,
            periods_per_year=periods_per_year,
        )
        pv_at_rate[label] = pv
        pv_percent_at_rate[label] = pv / equipment_cost * 100.0

    return EconomicsResult(
        stated_index_rate=stated_index_rate,
        solved_implicit_yield=solved,
        periods_per_year=periods_per_year,
        undiscounted_total_payments=payment * n_periods,
        pv_at_rate=pv_at_rate,
        pv_percent_at_rate=pv_percent_at_rate,
    )
