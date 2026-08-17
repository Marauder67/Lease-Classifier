"""Deterministic economics must reproduce the Davalor pilot numbers exactly."""

from app.engine.economics import compute_economics, present_value, solve_implicit_rate

COST = 586760.0
PMT = 11863.13
N = 60


def test_solved_implicit_yield_matches_report():
    rate = solve_implicit_rate(COST, PMT, N, timing="advance", buyout=1.0)
    # Report states ~8.17%; solver lands at 8.165%.
    assert abs(rate - 0.0817) < 0.0005


def test_pv_at_solved_rate_equals_cost():
    rate = solve_implicit_rate(COST, PMT, N, timing="advance", buyout=1.0)
    pv = present_value(PMT, N, rate, timing="advance", buyout=1.0)
    assert abs(pv - COST) < 1.0


def test_pv_percentages_match_report():
    econ = compute_economics(
        COST, PMT, N, timing="advance", buyout=1.0,
        stated_index_rate=0.0397, extra_rates={"ibr": 0.08},
    )
    pct = econ.pv_percent_at_rate
    assert abs(pct["stated_index"] - 110.2) < 0.2   # SOFR 3.97%
    assert abs(pct["ibr"] - 100.4) < 0.2            # 8% IBR
    assert abs(pct["solved_implicit"] - 100.0) < 0.1


def test_undiscounted_total():
    econ = compute_economics(COST, PMT, N, timing="advance", buyout=1.0)
    assert abs(econ.undiscounted_total_payments - 711787.80) < 0.01


def test_solver_raises_when_unsolvable():
    # Payments far below cost with tiny term cannot amortize -> no sign change.
    import pytest
    with pytest.raises(ValueError):
        solve_implicit_rate(1_000_000.0, 10.0, 3, timing="advance")
