"""Three-statement articulation helpers: the opening (Day-1) balance sheet and
the per-year income statement. Pure functions — no state, no I/O. The balance
sheet balances by construction (see the spec's balance proof); the balance check
in run_lbo is a bug detector, not load-bearing accounting.
"""


def opening_balance_sheet(entry_revenue: float, ev: float, total_debt: float,
                          sponsor_equity: float, a: dict) -> dict:
    """Day-1 post-deal balance sheet. Cash-free/debt-free convention: opening
    cash is zero and goodwill is the plug that makes Assets = Liabilities + Equity.
    """
    ppe = a["ppe_pct_of_revenue"] * entry_revenue
    nwc = a["nwc_pct_of_revenue"] * entry_revenue
    goodwill = ev - (ppe + nwc)
    return {"cash": 0.0, "nwc": nwc, "ppe": ppe, "goodwill": goodwill,
            "debt": total_debt, "equity": sponsor_equity}
