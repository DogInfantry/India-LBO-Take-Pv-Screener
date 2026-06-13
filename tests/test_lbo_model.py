from lbo_model import run_lbo


def base_assumptions(**overrides):
    """Minimal `lbo` assumptions dict for tests; override per case."""
    a = {
        "entry_multiple": 8.0,
        "tranches": [
            {"name": "senior", "turns": 2.0, "rate": 0.090, "mandatory_amort_pct": 0.10},
            {"name": "mezzanine", "turns": 1.0, "rate": 0.130, "mandatory_amort_pct": 0.0},
        ],
        "revolver_rate": 0.085,
        "ebitda_growth": 0.08,
        "hold_years": 5,
        "tax_rate": 0.25,
        "capex_pct_of_ebitda": 0.25,
        "wc_pct_of_incremental_ebitda": 0.20,
    }
    a.update(overrides)
    return a


def legacy_single_tranche():
    """Reproduces the pre-change model: one 3.0x bullet tranche at 9.5%."""
    return base_assumptions(tranches=[
        {"name": "term", "turns": 3.0, "rate": 0.095, "mandatory_amort_pct": 0.0},
    ])


def test_single_tranche_reproduces_legacy_numbers():
    res = run_lbo(1000.0, legacy_single_tranche())
    su = res["sources_uses"]
    assert abs(su["enterprise_value"] - 8000.0) < 1e-9
    assert abs(su["debt"] - 3000.0) < 1e-9
    assert abs(su["sponsor_equity"] - 5000.0) < 1e-9
    assert 1.0 < res["moic"] < 4.0
    assert abs((1 + res["irr"]) ** 5 - res["moic"]) < 1e-9


def test_sources_equal_uses():
    res = run_lbo(1000.0, base_assumptions())
    su = res["sources_uses"]
    assert abs(su["debt"] + su["sponsor_equity"] - su["enterprise_value"]) < 1e-9
    assert abs(sum(t["amount"] for t in su["tranches"]) - su["debt"]) < 1e-9


def test_mezz_principal_untouched_by_sweep_while_senior_outstanding():
    # Mezz has no mandatory amort, so any drop in its balance must be the sweep.
    res = run_lbo(1000.0, base_assumptions())
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
    res = run_lbo(1000.0, a)
    sched = res["schedule"]
    # Each year senior still has a balance, it must repay at least the
    # scheduled mandatory amount (sweep can add more on top).
    prev = original
    for _, r in sched.iterrows():
        if prev > 1e-6:
            assert r["senior_repaid"] >= min(scheduled, prev) - 1e-6
        prev = r["senior_ending"]
