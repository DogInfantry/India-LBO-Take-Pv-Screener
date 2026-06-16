from lbo_model import run_lbo


def base_assumptions(**overrides):
    """Minimal `lbo` assumptions dict (Phase 2 revenue-driven shape)."""
    a = {
        "entry_multiple": 8.0,
        "tranches": [
            {"name": "senior", "turns": 2.0, "rate": 0.090, "mandatory_amort_pct": 0.10},
            {"name": "mezzanine", "turns": 1.0, "rate": 0.130, "mandatory_amort_pct": 0.0},
        ],
        "revolver_rate": 0.085,
        "hold_years": 5,
        "tax_rate": 0.25,
        "revenue_growth": 0.08,
        "ppe_pct_of_revenue": 0.40,
        "da_pct_of_ppe": 0.10,
        "capex_pct_of_revenue": 0.05,
        "txn_fee_pct_of_ev": 0.020,
        "financing_fee_pct_of_debt": 0.025,
        "cogs_pct_of_revenue": 0.65,
        "working_capital": {"dso_days": 45, "dio_days": 60, "dpo_days": 40},
    }
    a.update(overrides)
    return a


def test_sources_equal_uses():
    res = run_lbo(5000.0, 1000.0, base_assumptions())
    su = res["sources_uses"]
    assert abs(su["debt"] + su["sponsor_equity"] - (su["enterprise_value"] + su["txn_fees"] + su["financing_fees"])) < 1e-9
    assert abs(sum(t["amount"] for t in su["tranches"]) - su["debt"]) < 1e-9


def test_mezz_principal_untouched_by_sweep_while_senior_outstanding():
    # Mezz has no mandatory amort, so any drop in its balance must be the sweep.
    res = run_lbo(5000.0, 1000.0, base_assumptions())
    sched = res["schedule"]
    for _, r in sched.iterrows():
        if r["senior_ending"] > 1e-6:
            # While senior is outstanding, mezz must not be swept at all.
            assert r["mezzanine_repaid"] < 1e-6, (
                f"year {r['year']}: mezz repaid {r['mezzanine_repaid']} "
                f"while senior still {r['senior_ending']}")


def test_senior_mandatory_amortization_each_year():
    a = base_assumptions()
    senior = a["tranches"][0]
    original = senior["turns"] * 1000.0           # 2.0x * 1000 EBITDA = 2000
    scheduled = senior["mandatory_amort_pct"] * original  # 10% * 2000 = 200
    res = run_lbo(5000.0, 1000.0, a)
    sched = res["schedule"]
    # Each year senior still has a balance, it must repay at least the
    # scheduled mandatory amount (sweep can add more on top).
    prev = original
    for _, r in sched.iterrows():
        if prev > 1e-6:
            assert r["senior_repaid"] >= min(scheduled, prev) - 1e-6
        prev = r["senior_ending"]


def test_rbi_cap_binds_and_scales_tranches_proportionally():
    # Low entry multiple + high leverage forces the 0.75 x EV cap to bind.
    a = base_assumptions()
    res = run_lbo(5000.0, 1000.0, a, entry_multiple=4.0, total_leverage=3.5)
    ev = 4000.0
    su = res["sources_uses"]
    assert abs(su["debt"] - 0.75 * ev) < 1e-9          # total capped at 75% of EV
    # Pre-cap turns were senior:mezz = 2.0:1.0 scaled to 3.5 total; the cap
    # scales both by the same factor, so the 2:1 ratio is preserved.
    senior = next(t for t in su["tranches"] if t["name"] == "senior")
    mezz = next(t for t in su["tranches"] if t["name"] == "mezzanine")
    assert abs(senior["amount"] / mezz["amount"] - 2.0) < 1e-9


def test_cap_does_not_bind_when_leverage_modest():
    res = run_lbo(5000.0, 1000.0, base_assumptions())  # 3.0x on 8.0x EV = 37.5%
    su = res["sources_uses"]
    assert abs(su["debt"] - 3000.0) < 1e-9


from lbo_model import sensitivity_grid


def test_grid_center_cell_matches_base_run():
    a = base_assumptions()
    base = run_lbo(5000.0, 1000.0, a)                 # base turns sum to 3.0
    irr, moic = sensitivity_grid(5000.0, 1000.0, a,
                                 entry_multiples=[6.0, 8.0, 10.0],
                                 leverage_multiples=[2.0, 3.0, 4.0])
    # Cell at entry 8.0 / total leverage 3.0 == the unscaled base run.
    assert abs(irr.loc[8.0, 3.0] - base["irr"]) < 1e-12
    assert abs(moic.loc[8.0, 3.0] - base["moic"]) < 1e-12


def test_grid_high_leverage_cell_triggers_cap():
    a = base_assumptions()
    irr, moic = sensitivity_grid(5000.0, 1000.0, a,
                                 entry_multiples=[4.0],
                                 leverage_multiples=[3.5])
    # 3.5x on a 4.0x EV would be 87.5% > 75%; cap binds but run still returns a number.
    import math
    assert not math.isnan(moic.loc[4.0, 3.5])


def test_balance_sheet_balances_every_year():
    res = run_lbo(5000.0, 1000.0, base_assumptions())
    assert res["max_balance_error"] < 1e-6
    bs = res["balance_sheet"]
    assert (bs["year"] == 0).any()
    assert bs["balance_error"].abs().max() < 1e-6
