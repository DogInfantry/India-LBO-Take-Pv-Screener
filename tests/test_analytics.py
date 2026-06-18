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


def test_sobol_indices_reproducible():
    # Seeded SALib sampler => identical indices across calls (deterministic contract).
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    s1 = analytics.sobol_indices(inp, n=256)
    s2 = analytics.sobol_indices(inp, n=256)
    assert s1["total_order"] == s2["total_order"]
    assert s1["first_order"] == s2["first_order"]


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


def test_delisting_model_structure():
    cfg = base_cfg(); row = sample_row()
    inp = analytics.company_inputs(row, cfg)
    d = analytics.delisting_model(inp, row, cfg)
    assert d["acceptance_threshold_pct"] == 90.0
    # public float that must tender = 90 - promoter_holding
    assert d["float_to_tender_pct"] == pytest.approx(90.0 - 62.0)
    assert d["indicative"] is True


def test_company_block_has_canonical_keys():
    cfg = base_cfg(); row = sample_row()
    block = analytics.build_company_block(row, cfg)
    assert set(block) == set(analytics.COMPANY_KEYS)
    assert block["returns"]["irr"] is not None
    assert "income" in block["statements"]


# ---------------------------------------------------------------------------
# Task 12: build_results + JSON-safe serialization
# ---------------------------------------------------------------------------
import json


def test_build_results_is_json_safe_and_consistent():
    # uses the committed snapshot (no network): gather(no_fetch=True)
    import sys, pathlib
    from datetime import date
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
    from export_site import gather
    cfg, _universe, results_df = gather(no_fetch=True)   # NB: (cfg, universe, results)
    payload = analytics.build_results(results_df, cfg, date.today().isoformat())
    text = json.dumps(payload)                       # must not raise
    assert "NaN" not in text and "Infinity" not in text
    # every passer summary has a matching company block
    assert set(c["ticker"] for c in payload["passers"]) == set(payload["companies"])


# ---------------------------------------------------------------------------
# Task 13: tools/export_data.py CLI
# ---------------------------------------------------------------------------


def test_export_data_writes_valid_json(tmp_path):
    import sys, pathlib, json, subprocess
    out = tmp_path / "results.json"
    root = pathlib.Path(__file__).resolve().parent.parent
    subprocess.run([sys.executable, str(root / "tools" / "export_data.py"),
                    "--no-fetch", "--out", str(out)], check=True, cwd=root)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "passers" in data and "companies" in data and data["as_of"]


def test_degenerate_company_block_is_flagged_not_absurd():
    # Net cash > market cap -> negative EV (the JUSTDIAL case). The LBO is not
    # computable; the block must flag it and null the returns, not emit 8680x.
    cfg = base_cfg()
    row = sample_row().copy()
    row["ticker"] = "NETCASH.NS"
    row["market_cap_cr"] = 1000.0
    row["net_debt_cr"] = -2000.0
    block = analytics.build_company_block(row, cfg)
    assert set(block) == set(analytics.COMPANY_KEYS)        # contract shape preserved
    assert block["returns"]["degenerate"] is True
    assert block["returns"]["irr"] is None
    assert block["returns"]["moic"] is None
    assert block["montecarlo"] is None and block["solvers"] is None
    import json
    json.dumps(block)                                       # serializes cleanly


def test_sensitivity_grid_premium_exit_shape_and_monotonicity():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    premiums = [0.0, 10.0, 20.0, 30.0]
    em = inp["entry_ev"] / inp["entry_ebitda"]
    exits = [round(em - 1, 1), round(em, 1), round(em + 1, 1)]
    g = analytics.sensitivity_grid_premium_exit(inp, premiums, exits)
    assert g["premiums_pct"] == premiums
    assert g["exit_multiples"] == exits
    assert len(g["irr"]) == len(premiums)              # rows = premiums
    assert all(len(row) == len(exits) for row in g["irr"])
    # IRR falls as premium rises (more expensive entry), holding exit fixed
    col0 = [g["irr"][i][0] for i in range(len(premiums))]
    assert col0[0] > col0[-1]
    # IRR matches a direct run_lbo at a sampled cell
    ev = inp["market_cap"] * (1 + premiums[1] / 100.0) + inp["net_debt"]
    direct = analytics.run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                               entry_ev=ev, total_leverage=inp["total_leverage"],
                               exit_multiple=exits[2])["irr"]
    assert g["irr"][1][2] == pytest.approx(direct, abs=1e-9)


def test_company_block_sensitivity_has_grid():
    cfg = base_cfg(); block = analytics.build_company_block(sample_row(), cfg)
    assert "iso_frontier" in block["sensitivity"]
    g = block["sensitivity"]["grid"]
    assert len(g["premiums_pct"]) == len(cfg["sensitivity"]["premiums_pct"])
    assert len(g["exit_multiples"]) == 5
    assert len(g["irr"]) == len(g["premiums_pct"])


# ---------------------------------------------------------------------------
# Task 2: scenario_block() — Bull / Base / Bear
# ---------------------------------------------------------------------------


def scenarios_cfg():
    """Extend base_cfg with a scenarios block."""
    cfg = base_cfg()
    cfg["scenarios"] = {
        "bull": {"revenue_growth_delta": 0.08, "margin_delta": 0.05, "exit_multiple_delta": 2.0},
        "bear": {"revenue_growth_delta": -0.05, "margin_delta": -0.05, "exit_multiple_delta": -2.0},
    }
    return cfg


def test_scenario_block_has_three_keys():
    block = analytics.scenario_block(
        analytics.company_inputs(sample_row(), scenarios_cfg()),
        scenarios_cfg(),
    )
    assert set(block.keys()) == {"bull", "base", "bear"}


def test_scenario_block_base_matches_run_lbo():
    """Base scenario (zero deltas) must reproduce the direct run_lbo call exactly."""
    from lbo_model import run_lbo
    cfg = scenarios_cfg()
    inp = analytics.company_inputs(sample_row(), cfg)
    block = analytics.scenario_block(inp, cfg)
    base = block["base"]
    assert base is not None
    res = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                  entry_ev=inp["entry_ev"], total_leverage=inp["total_leverage"])
    assert base["returns"]["irr"] == pytest.approx(res["irr"], rel=1e-6)
    assert base["returns"]["moic"] == pytest.approx(res["moic"], rel=1e-6)
    assert base["financials"]["revenue"] == pytest.approx(
        res["income_statement"].iloc[-1]["revenue"], rel=1e-6)


def test_scenario_block_bull_gt_base_gt_bear():
    """For a healthy company, bull IRR > base IRR > bear IRR."""
    cfg = scenarios_cfg()
    inp = analytics.company_inputs(sample_row(), cfg)
    block = analytics.scenario_block(inp, cfg)
    bull_irr = block["bull"]["returns"]["irr"]
    base_irr = block["base"]["returns"]["irr"]
    bear_irr = block["bear"]["returns"]["irr"]
    assert bull_irr is not None and base_irr is not None
    assert bull_irr > base_irr
    if bear_irr is not None:   # bear may be degenerate for some inputs
        assert base_irr > bear_irr


def test_scenario_block_zero_ebitda_clamp_returns_none():
    """A margin_delta so negative that sc_ebitda clamps to 0 must return None, not crash."""
    cfg = scenarios_cfg()
    cfg["scenarios"]["bear"]["margin_delta"] = -99.0   # guaranteed to zero out ebitda
    inp = analytics.company_inputs(sample_row(), cfg)
    block = analytics.scenario_block(inp, cfg)
    assert block["bear"] is None          # clamped -> skipped, not an exception
    assert block["base"] is not None      # base unaffected
