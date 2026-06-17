# src/analytics.py
"""Advanced-quant layer for the LBO showcase.

Every function here only *calls* run_lbo (and the screener); none of the
existing model math is modified. Pure and import-safe (no Streamlit), so the
exporter and pytest can import it freely.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from lbo_model import run_lbo

HURDLE_IRR = 0.20
MC_N = 5000
SOBOL_N = 1024
SEED = 42


def company_inputs(row: pd.Series, cfg: dict) -> dict:
    """Derive the inputs run_lbo needs for one screener row (take-private price)."""
    lbo = cfg["lbo"]
    prem = lbo["control_premium_pct"]
    total_leverage = sum(t["turns"] for t in lbo["tranches"])
    market_cap = float(row["market_cap_cr"])
    net_debt = float(row["net_debt_cr"])
    entry_ev = market_cap * (1 + prem / 100.0) + net_debt
    return {
        "entry_revenue": float(row["revenue_cr"]),
        "entry_ebitda": float(row["ebitda_cr"]),
        "assumptions": lbo,
        "market_cap": market_cap,
        "net_debt": net_debt,
        "premium_pct": prem,
        "total_leverage": total_leverage,
        "entry_ev": entry_ev,
    }
