from statements import opening_balance_sheet, income_statement_row


def ratios():
    return {"ppe_pct_of_revenue": 0.40, "nwc_pct_of_revenue": 0.15,
            "da_pct_of_ppe": 0.10, "capex_pct_of_revenue": 0.05,
            "tax_rate": 0.25}


def test_opening_balance_sheet_balances():
    # EV 8000, debt 3000, equity 5000, entry revenue 5000.
    bs = opening_balance_sheet(5000.0, 8000.0, 3000.0, 5000.0, ratios())
    assert bs["cash"] == 0.0
    assert abs(bs["ppe"] - 2000.0) < 1e-9          # 0.40 * 5000
    assert abs(bs["nwc"] - 750.0) < 1e-9           # 0.15 * 5000
    assert abs(bs["goodwill"] - (8000.0 - 2000.0 - 750.0)) < 1e-9
    assets = bs["cash"] + bs["nwc"] + bs["ppe"] + bs["goodwill"]
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


def test_income_statement_taxes_floored_at_zero():
    # Huge interest drives EBT negative; taxes must floor at zero.
    isr = income_statement_row(1000.0, 0.20, 2000.0, 5000.0, ratios())
    assert isr["ebt"] < 0
    assert isr["taxes"] == 0.0
    assert abs(isr["net_income"] - isr["ebt"]) < 1e-9
