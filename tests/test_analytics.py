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
        "interest_coverage": 8.0, "fcf_cr": 600.0, "fcf_yield": 0.06,
        "promoter_holding_pct": 62.0, "promoter_pledge_pct": 1.0,
        "market_cap_cr": 9000.0, "unused_debt_capacity_cr": 2500.0, "latest_year": 2025,
    })


def test_company_inputs_prices_take_private_ev():
    inp = analytics.company_inputs(sample_row(), base_cfg())
    # entry_ev = market_cap*(1+prem) + net_debt = 9000*1.25 + 500 = 11750
    assert inp["entry_ev"] == pytest.approx(11750.0)
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
