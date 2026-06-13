from statements import opening_balance_sheet, income_statement_row, working_capital


def ratios():
    return {"ppe_pct_of_revenue": 0.40,
            "da_pct_of_ppe": 0.10, "capex_pct_of_revenue": 0.05,
            "tax_rate": 0.25,
            "txn_fee_pct_of_ev": 0.020,
            "financing_fee_pct_of_debt": 0.025,
            "cogs_pct_of_revenue": 0.65,
            "working_capital": {"dso_days": 45, "dio_days": 60, "dpo_days": 40}}


def test_opening_balance_sheet_balances_with_fees():
    a = ratios()
    # EV 8000, debt 3000, entry revenue 5000, txn 160 (2% of EV), fin 75 (2.5% of debt).
    txn_fees, financing_fees = 160.0, 75.0
    equity = 8000.0 + txn_fees + financing_fees - 3000.0  # uses - debt
    bs = opening_balance_sheet(5000.0, 8000.0, 3000.0, equity, a,
                               txn_fees=txn_fees, financing_fees=financing_fees)
    wc = working_capital(5000.0, a)
    assert bs["cash"] == 0.0
    assert abs(bs["ppe"] - 2000.0) < 1e-9                 # 0.40 * 5000
    assert abs(bs["nwc"] - wc["nwc"]) < 1e-9              # days-based
    assert abs(bs["dfc"] - financing_fees) < 1e-9
    assert abs(bs["goodwill"] - (8000.0 + txn_fees - 2000.0 - wc["nwc"])) < 1e-9
    assets = bs["cash"] + bs["nwc"] + bs["ppe"] + bs["goodwill"] + bs["dfc"]
    assert abs(assets - (bs["debt"] + bs["equity"])) < 1e-9   # balances


def test_income_statement_ties():
    # revenue 5400, margin 0.20, opening PP&E 2000, interest 300.
    isr = income_statement_row(5400.0, 0.20, 2000.0, 300.0, ratios())
    assert abs(isr["ebitda"] - 1080.0) < 1e-9      # 5400 * 0.20
    assert abs(isr["da"] - 200.0) < 1e-9           # 0.10 * 2000
    assert abs(isr["ebit"] - (1080.0 - 200.0)) < 1e-9
    assert abs(isr["ebt"] - (880.0 - 300.0)) < 1e-9
    assert abs(isr["taxes"] - 0.25 * 580.0) < 1e-9
    assert abs(isr["net_income"] - (580.0 - 0.25 * 580.0)) < 1e-9
    assert isr["dfc_amort"] == 0.0


def test_income_statement_includes_dfc_amortization():
    a = ratios()
    # revenue 5400, margin 0.20, opening PP&E 2000, interest 300, dfc_amort 15.
    isr = income_statement_row(5400.0, 0.20, 2000.0, 300.0, a, dfc_amort=15.0)
    assert abs(isr["dfc_amort"] - 15.0) < 1e-9
    # EBITDA 1080, D&A 200, dfc 15, interest 300 -> EBT = 1080-200-15-300 = 565
    assert abs(isr["ebt"] - 565.0) < 1e-9
    assert abs(isr["taxes"] - 0.25 * 565.0) < 1e-9
    assert abs(isr["net_income"] - (565.0 - 0.25 * 565.0)) < 1e-9


def test_income_statement_taxes_floored_at_zero():
    # Huge interest drives EBT negative; taxes must floor at zero.
    isr = income_statement_row(1000.0, 0.20, 2000.0, 5000.0, ratios())
    assert isr["ebt"] < 0
    assert isr["taxes"] == 0.0
    assert abs(isr["net_income"] - isr["ebt"]) < 1e-9


# conftest.py puts src/ on the path; pytest's prepend import mode puts tests/ there.
from lbo_model import run_lbo
from test_lbo_model import base_assumptions  # reuse the Phase 2 fixture


def model():
    return run_lbo(5000.0, 1000.0, base_assumptions())


def test_cash_flow_reconciles_to_balance_sheet_cash():
    res = model()
    cf = res["cash_flow"].set_index("year")
    bs = res["balance_sheet"].set_index("year")
    for year in cf.index:
        assert abs(cf.loc[year, "ending_cash"] - bs.loc[year, "cash"]) < 1e-6


def test_ppe_roll_forward():
    res = model()
    bs = res["balance_sheet"].set_index("year")
    cf = res["cash_flow"].set_index("year")
    is_ = res["income_statement"].set_index("year")
    for year in cf.index:
        expected = bs.loc[year - 1, "ppe"] + cf.loc[year, "capex"] - is_.loc[year, "da"]
        assert abs(bs.loc[year, "ppe"] - expected) < 1e-6


def test_retained_earnings_accumulate():
    res = model()
    bs = res["balance_sheet"].set_index("year")
    is_ = res["income_statement"].set_index("year")
    sponsor_equity = res["sources_uses"]["sponsor_equity"]
    cumulative = sponsor_equity
    for year in is_.index:
        cumulative += is_.loc[year, "net_income"]
        assert abs(bs.loc[year, "equity"] - cumulative) < 1e-6


def test_goodwill_held_flat():
    res = model()
    gw = res["balance_sheet"]["goodwill"]
    assert gw.nunique() == 1


from statements import working_capital


def test_working_capital_days_based():
    a = ratios()  # dso 45, dio 60, dpo 40, cogs 0.65
    wc = working_capital(10000.0, a)
    assert abs(wc["ar"] - 45 / 365 * 10000.0) < 1e-9
    assert abs(wc["inventory"] - 60 / 365 * 0.65 * 10000.0) < 1e-9
    assert abs(wc["ap"] - 40 / 365 * 0.65 * 10000.0) < 1e-9
    assert abs(wc["nwc"] - (wc["ar"] + wc["inventory"] - wc["ap"])) < 1e-12
