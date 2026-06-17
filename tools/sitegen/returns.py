"""Base-case returns for ranked survivors — standalone copy of the app's
`base_case_returns` (src/app.py:81), kept here so the exporter never imports the
(import-unsafe) Streamlit module. Parity with src/ is asserted by the tests.
"""

import pandas as pd
from lbo_model import run_lbo


def base_case_returns(passed: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Run the base-case market take-private LBO (config control premium, base
    leverage, config growth) for each screen survivor and rank by IRR.

    Skips names without live market data. Flags degenerate (near-zero/negative
    EV) names with NaN returns so they rank last and render as 'n.m.'.
    """
    lbo_cfg = cfg["lbo"]
    prem = lbo_cfg.get("control_premium_pct", 25.0)
    base_lev = sum(t["turns"] for t in lbo_cfg["tranches"])
    rows = []
    for _, r in passed.iterrows():
        if pd.isna(r["market_cap_cr"]) or pd.isna(r["net_debt_cr"]):
            continue
        entry_ev = r["market_cap_cr"] * (1 + prem / 100) + r["net_debt_cr"]
        out = run_lbo(r["revenue_cr"], r["ebitda_cr"], lbo_cfg,
                      entry_ev=entry_ev, total_leverage=base_lev)
        degenerate = entry_ev <= 0.05 * r["ebitda_cr"]
        rows.append({
            "name": r["ticker"].replace(".NS", ""),
            "implied_mult": out["entry_multiple"],
            "irr": float("nan") if degenerate else out["irr"],
            "moic": float("nan") if degenerate else out["moic"],
            "equity_cr": out["sources_uses"]["sponsor_equity"],
            "entry_ev_cr": entry_ev,
            "degenerate": degenerate,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("irr", ascending=False, na_position="last") \
             .reset_index(drop=True)
