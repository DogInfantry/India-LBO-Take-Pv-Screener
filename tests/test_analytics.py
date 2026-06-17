# tests/test_analytics.py
import math
import pandas as pd
import pytest

import analytics


def base_cfg():
    """Minimal config mirroring config/config.yaml's lbo + screening blocks."""
    return {
        "lbo": {
            "entry_multiple": 8.0,
            "control_premium_pct": 25.0,
            "tranches": [
                {"name": "senior", "turns": 2.0, "rate": 0.090, "mandatory_amort_pct": 0.10},
                {"name": "mezzanine", "turns": 1.0, "rate": 0.130, "mandatory_amort_pct": 0.0},
            ],
            "revolver_rate": 0.085, "hold_years": 5, "tax_rate": 0.25,
            "revenue_growth": 0.08, "ppe_pct_of_revenue": 0.40, "da_pct_of_ppe": 0.10,
            "capex_pct_of_revenue": 0.05, "txn_fee_pct_of_ev": 0.020,
            "financing_fee_pct_of_debt": 0.025, "cogs_pct_of_revenue": 0.65,
            "working_capital": {"dso_days": 45, "dio_days": 60, "dpo_days": 40},
        },
        "screening": {"min_interest_coverage": 3.0,
                      "min_promoter_holding_pct": 50.0, "max_promoter_holding_pct": 75.0,
                      "max_promoter_pledge_pct": 5.0},
        "sensitivity": {"premiums_pct": [0.0, 10.0, 20.0, 30.0, 40.0],
                        "leverage_multiples": [2.0, 2.5, 3.0, 3.5, 4.0]},
    }


def sample_row():
    """A synthetic passer with healthy headroom (clears the hurdle comfortably)."""
    return pd.Series({
        "ticker": "TEST.NS", "revenue_cr": 5000.0, "ebitda_cr": 1000.0,
        "ebitda_margin": 0.20, "net_debt_cr": 500.0, "net_debt_to_ebitda": 0.5,
        "interest_coverage": 8.0, "fcf_cr": 600.0, "fcf_yield": 0.13,
        "promoter_holding_pct": 62.0, "promoter_pledge_pct": 1.0,
        "market_cap_cr": 4500.0, "unused_debt_capacity_cr": 2500.0, "latest_year": 2025,
    })


def test_company_inputs_prices_take_private_ev():
    inp = analytics.company_inputs(sample_row(), base_cfg())
    # entry_ev = market_cap*(1+prem) + net_debt = 4500*1.25 + 500 = 6125
    assert inp["entry_ev"] == pytest.approx(6125.0)
    assert inp["entry_revenue"] == 5000.0
    assert inp["entry_ebitda"] == 1000.0
    assert inp["total_leverage"] == pytest.approx(3.0)   # 2.0 + 1.0 turns
    assert inp["premium_pct"] == 25.0
    assert inp["assumptions"] is base_cfg()["lbo"] or "tranches" in inp["assumptions"]


def test_monte_carlo_reproducible_and_bounded():
    cfg = base_cfg()
    inp = analytics.company_inputs(sample_row(), cfg)
    a = analytics.monte_carlo(inp, n=500, seed=7)
    b = analytics.monte_carlo(inp, n=500, seed=7)
    assert a["irr"][:5] == b["irr"][:5]            # same seed -> same draws
    assert len(a["irr"]) == len(a["moic"]) == 500
    assert 0.0 <= a["p_beat_hurdle"] <= 1.0


def test_downside_risk_ordering():
    cfg = base_cfg()
    inp = analytics.company_inputs(sample_row(), cfg)
    mc = analytics.monte_carlo(inp, n=2000, seed=1)
    d = analytics.downside_risk(mc)
    assert 0.0 <= d["p_loss"] <= 1.0
    assert d["cvar5_moic"] <= d["var5_moic"]        # tail mean <= the 5% quantile


def test_irr_bridge_steps_sum_to_total():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    br = analytics.irr_bridge(inp)
    total = br["deleveraging"] + br["ebitda_growth"] + br["multiple_rerating"]
    assert total == pytest.approx(br["total_irr"], abs=1e-6)

def test_value_bridge_reconciles_equity():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    vb = analytics.value_bridge(inp)
    built = (vb["entry_equity"] + vb["ebitda_growth"] + vb["multiple_change"]
             + vb["debt_paydown"] + vb["fees_and_other"])
    assert built == pytest.approx(vb["exit_equity"], rel=1e-6)


def test_max_bid_lands_on_hurdle():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    sol = analytics.max_bid_solver(inp, target_irr=0.20)
    assert sol["converged"]
    # re-price at the solved premium and confirm IRR ~ target
    from lbo_model import run_lbo
    ev = inp["market_cap"] * (1 + sol["max_premium_pct"] / 100.0) + inp["net_debt"]
    irr = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                  entry_ev=ev, total_leverage=inp["total_leverage"])["irr"]
    assert irr == pytest.approx(0.20, abs=2e-3)

def test_max_bid_no_solution_when_unaffordable():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    sol = analytics.max_bid_solver(inp, target_irr=0.99)  # impossible hurdle
    assert sol["converged"] is False


def test_debt_capacity_is_binding():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    cov = cfg["screening"]["min_interest_coverage"]
    sol = analytics.debt_capacity_solver(inp, min_coverage=cov)
    assert sol["converged"]
    # at the solved leverage, min annual coverage >= covenant
    assert sol["min_coverage_at_max"] >= cov - 1e-6
    # one notch higher breaches
    higher = analytics._min_coverage(inp, sol["max_leverage"] + 0.05)
    assert higher < cov


def test_optimal_exit_within_range():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    sol = analytics.optimal_exit(inp)
    years = [r["year"] for r in sol["by_year"]]
    assert years == [1, 2, 3, 4, 5]
    assert 1 <= sol["best_year"] <= 5


def test_sobol_indices_keys_and_ranges():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    s = analytics.sobol_indices(inp, n=256)   # small N for test speed
    for k in ("revenue_growth", "ebitda_shock", "exit_multiple"):
        assert k in s["total_order"] and k in s["first_order"]
    # total-order >= first-order (within numerical noise) for each driver
    for k in s["first_order"]:
        assert s["total_order"][k] >= s["first_order"][k] - 0.05


def test_iso_frontier_points_hit_target():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    fr = analytics.iso_irr_frontier(inp, target_irr=0.20)
    assert fr["target_irr"] == 0.20
    from lbo_model import run_lbo
    for pt in fr["points"]:
        ev = inp["market_cap"] * (1 + pt["premium_pct"] / 100.0) + inp["net_debt"]
        irr = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                      entry_ev=ev, total_leverage=inp["total_leverage"],
                      exit_multiple=pt["exit_multiple"])["irr"]
        assert irr == pytest.approx(0.20, abs=5e-3)


def test_feasibility_score_range_and_pledge_monotonicity():
    cfg = base_cfg(); row = sample_row()
    s_low_pledge = analytics.feasibility_score(row, cfg)
    high = row.copy(); high["promoter_pledge_pct"] = 20.0
    s_high_pledge = analytics.feasibility_score(high, cfg)
    assert 0 <= s_low_pledge["score"] <= 100
    assert s_high_pledge["score"] < s_low_pledge["score"]   # more pledge -> less feasible
    assert set(s_low_pledge["components"]) >= {"holding", "pledge", "float", "valuation"}
