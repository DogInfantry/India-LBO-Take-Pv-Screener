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
from SALib.sample import saltelli
from SALib.analyze import sobol as sobol_analyze

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


def _entry_multiple(inp: dict) -> float:
    return inp["entry_ev"] / inp["entry_ebitda"] if inp["entry_ebitda"] else 0.0


def monte_carlo(inp: dict, n: int = MC_N, seed: int = SEED,
                hurdle: float = HURDLE_IRR) -> dict:
    """Distribution of IRR/MOIC over growth, EBITDA-margin and exit-multiple draws."""
    rng = np.random.default_rng(seed)
    a = inp["assumptions"]
    base_g = a["revenue_growth"]
    em = _entry_multiple(inp)

    growth = np.clip(rng.normal(base_g, 0.03, n), 0.0, 2 * base_g)
    shock = np.clip(rng.normal(1.0, 0.05, n), 0.7, 1.3)
    exit_mult = np.clip(rng.normal(em, 1.0, n), max(1.0, em - 3), em + 3)

    irrs, moics = [], []
    for g, s, xm in zip(growth, shock, exit_mult):
        res = run_lbo(inp["entry_revenue"], inp["entry_ebitda"] * s,
                      {**a, "revenue_growth": float(g)},
                      entry_ev=inp["entry_ev"], total_leverage=inp["total_leverage"],
                      exit_multiple=float(xm))
        irrs.append(res["irr"])
        moics.append(res["moic"])

    irr_arr = np.array(irrs, dtype=float)
    finite = irr_arr[np.isfinite(irr_arr)]
    p_beat = float((finite >= hurdle).mean()) if finite.size else 0.0
    return {"irr": [None if not math.isfinite(x) else float(x) for x in irrs],
            "moic": [None if not math.isfinite(x) else float(x) for x in moics],
            "p_beat_hurdle": p_beat,
            "params": {"n": n, "seed": seed, "hurdle": hurdle,
                       "growth_sd": 0.03, "ebitda_shock_sd": 0.05, "exit_mult_sd": 1.0}}


def downside_risk(mc: dict, hurdle: float = HURDLE_IRR) -> dict:
    """P(capital impairment), 5% VaR and CVaR (expected shortfall) on MOIC."""
    moic = np.array([m for m in mc["moic"] if m is not None], dtype=float)
    if moic.size == 0:
        return {"p_loss": None, "var5_moic": None, "cvar5_moic": None}
    var5 = float(np.percentile(moic, 5))
    tail = moic[moic <= var5]
    return {"p_loss": float((moic < 1.0).mean()),
            "var5_moic": var5,
            "cvar5_moic": float(tail.mean()) if tail.size else var5}


def irr_bridge(inp: dict) -> dict:
    """IRR attributed cumulatively to deleveraging, then growth, then re-rating."""
    a = inp["assumptions"]; em = _entry_multiple(inp)
    common = dict(entry_ev=inp["entry_ev"], total_leverage=inp["total_leverage"])

    delever = run_lbo(inp["entry_revenue"], inp["entry_ebitda"],
                      {**a, "revenue_growth": 0.0}, exit_multiple=em, **common)["irr"]
    plus_growth = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], a,
                          exit_multiple=em, **common)["irr"]
    full = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], a, **common)["irr"]
    return {"deleveraging": delever,
            "ebitda_growth": plus_growth - delever,
            "multiple_rerating": full - plus_growth,
            "total_irr": full}


def value_bridge(inp: dict) -> dict:
    """Absolute (Rs cr) equity value creation, decomposed."""
    a = inp["assumptions"]
    res = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], a,
                  entry_ev=inp["entry_ev"], total_leverage=inp["total_leverage"])
    entry_em = res["entry_multiple"]; exit_em = res["exit_multiple"]
    ebitda_entry = inp["entry_ebitda"]
    ebitda_exit = res["income_statement"].iloc[-1]["ebitda"]
    entry_equity = res["sources_uses"]["sponsor_equity"]
    # entry EV is funded by sponsor equity + entry net debt (+ fees); so the
    # net-debt-at-entry the bridge pays down is EV minus sponsor equity.
    entry_net_debt = inp["entry_ev"] - entry_equity
    ebitda_growth = (ebitda_exit - ebitda_entry) * entry_em
    multiple_change = ebitda_exit * (exit_em - entry_em)
    debt_paydown = entry_net_debt - res["exit_net_debt"]
    exit_equity = res["exit_equity"]
    fees_and_other = exit_equity - (entry_equity + ebitda_growth + multiple_change + debt_paydown)
    return {"entry_equity": entry_equity, "ebitda_growth": ebitda_growth,
            "multiple_change": multiple_change, "debt_paydown": debt_paydown,
            "fees_and_other": fees_and_other, "exit_equity": exit_equity}


def _irr_at_premium(inp: dict, prem_pct: float) -> float:
    ev = inp["market_cap"] * (1 + prem_pct / 100.0) + inp["net_debt"]
    return run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                   entry_ev=ev, total_leverage=inp["total_leverage"])["irr"]


def max_bid_solver(inp: dict, target_irr: float = HURDLE_IRR,
                   lo: float = 0.0, hi: float = 100.0, tol: float = 1e-3) -> dict:
    """Highest control premium (%) at which IRR still >= target_irr."""
    f_lo, f_hi = _irr_at_premium(inp, lo), _irr_at_premium(inp, hi)
    if not math.isfinite(f_lo) or f_lo < target_irr:
        return {"converged": False, "reason": "cannot clear hurdle at any premium",
                "max_premium_pct": None, "max_ev": None}
    if f_hi >= target_irr:                      # clears even at the top of the range
        return {"converged": True, "max_premium_pct": hi,
                "max_ev": inp["market_cap"] * (1 + hi / 100.0) + inp["net_debt"]}
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if _irr_at_premium(inp, mid) >= target_irr:
            lo = mid
        else:
            hi = mid
    prem = lo
    return {"converged": True, "max_premium_pct": prem,
            "max_ev": inp["market_cap"] * (1 + prem / 100.0) + inp["net_debt"]}


def _min_coverage(inp: dict, leverage: float) -> float:
    sched = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                    entry_ev=inp["entry_ev"], total_leverage=leverage)["schedule"]
    cov = sched["ebitda"] / sched["interest"].replace(0, np.nan)
    return float(cov.min())


def debt_capacity_solver(inp: dict, min_coverage: float,
                         lo: float = 0.0, hi: float = 8.0, tol: float = 1e-2) -> dict:
    """Max total leverage (turns) keeping min annual interest-coverage >= covenant."""
    if _min_coverage(inp, lo) < min_coverage:
        return {"converged": False, "reason": "covenant breached even unlevered",
                "max_leverage": None, "min_coverage_at_max": None}
    if _min_coverage(inp, hi) >= min_coverage:
        return {"converged": True, "max_leverage": hi,
                "min_coverage_at_max": _min_coverage(inp, hi)}
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if _min_coverage(inp, mid) >= min_coverage:
            lo = mid
        else:
            hi = mid
    return {"converged": True, "max_leverage": lo,
            "min_coverage_at_max": _min_coverage(inp, lo)}


def sobol_indices(inp: dict, n: int = SOBOL_N) -> dict:
    a = inp["assumptions"]; base_g = a["revenue_growth"]; em = _entry_multiple(inp)
    problem = {
        "num_vars": 3,
        "names": ["revenue_growth", "ebitda_shock", "exit_multiple"],
        "bounds": [[max(0.0, base_g - 0.06), base_g + 0.06],
                   [0.85, 1.15],
                   [max(1.0, em - 3), em + 3]],
    }
    X = saltelli.sample(problem, n, calc_second_order=False)
    Y = np.empty(X.shape[0])
    for i, (g, s, xm) in enumerate(X):
        Y[i] = run_lbo(inp["entry_revenue"], inp["entry_ebitda"] * s,
                       {**a, "revenue_growth": float(g)},
                       entry_ev=inp["entry_ev"], total_leverage=inp["total_leverage"],
                       exit_multiple=float(xm))["irr"]
    Y = np.nan_to_num(Y, nan=float(np.nanmean(Y)))
    Si = sobol_analyze.analyze(problem, Y, calc_second_order=False)
    names = problem["names"]
    return {"first_order": {n_: float(v) for n_, v in zip(names, Si["S1"])},
            "total_order": {n_: float(v) for n_, v in zip(names, Si["ST"])}}


def optimal_exit(inp: dict) -> dict:
    a = inp["assumptions"]; n = a["hold_years"]
    by_year = []
    for k in range(1, n + 1):
        res = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], {**a, "hold_years": k},
                      entry_ev=inp["entry_ev"], total_leverage=inp["total_leverage"])
        by_year.append({"year": k, "irr": res["irr"], "moic": res["moic"]})
    valid = [r for r in by_year if r["irr"] is not None and math.isfinite(r["irr"])]
    best = max(valid, key=lambda r: r["irr"])["year"] if valid else None
    return {"by_year": by_year, "best_year": best}


def iso_irr_frontier(inp: dict, target_irr: float = HURDLE_IRR,
                     exit_multiples: list[float] | None = None) -> dict:
    em = _entry_multiple(inp)
    if exit_multiples is None:
        exit_multiples = [round(em - 2 + i, 1) for i in range(5)]  # em-2 .. em+2
    points = []
    for xm in exit_multiples:
        lo, hi = 0.0, 100.0
        def irr_at(p, xm=xm):
            ev = inp["market_cap"] * (1 + p / 100.0) + inp["net_debt"]
            return run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                           entry_ev=ev, total_leverage=inp["total_leverage"],
                           exit_multiple=xm)["irr"]
        if irr_at(lo) < target_irr or irr_at(hi) > target_irr:
            continue                       # no crossing in range for this exit multiple
        while hi - lo > 1e-2:
            mid = (lo + hi) / 2.0
            if irr_at(mid) >= target_irr: lo = mid
            else: hi = mid
        points.append({"exit_multiple": xm, "premium_pct": round(lo, 2)})
    return {"target_irr": target_irr, "points": points}


def _band_score(x, lo, hi):
    """100 inside [lo,hi], decaying linearly outside (width = the band)."""
    if x is None: return 0.0
    if lo <= x <= hi: return 100.0
    width = (hi - lo) or 1.0
    d = (lo - x) if x < lo else (x - hi)
    return max(0.0, 100.0 - 100.0 * d / width)


def feasibility_score(row: pd.Series, cfg: dict) -> dict:
    scr = cfg["screening"]
    holding = row.get("promoter_holding_pct")
    pledge = row.get("promoter_pledge_pct")
    # holding in the controllable sweet spot (>= min, <= SEBI ceiling)
    s_holding = _band_score(holding, scr["min_promoter_holding_pct"], scr["max_promoter_holding_pct"])
    # pledge: 100 at 0, 0 at the screen's max
    s_pledge = max(0.0, 100.0 * (1 - (pledge or 0.0) / max(scr["max_promoter_pledge_pct"], 1e-9)))
    s_pledge = min(100.0, s_pledge)
    # enough public float to actually clear the 90% delisting threshold
    public_float = 100.0 - (holding or 0.0)
    s_float = _band_score(public_float, 10.0, 50.0)
    # valuation: higher fcf_yield = cheaper = more feasible (cap at 12%)
    s_val = min(100.0, max(0.0, (row.get("fcf_yield") or 0.0) / 0.12 * 100.0))
    weights = {"holding": 0.40, "pledge": 0.25, "float": 0.20, "valuation": 0.15}
    comps = {"holding": s_holding, "pledge": s_pledge, "float": s_float, "valuation": s_val}
    score = round(sum(weights[k] * comps[k] for k in weights))
    return {"score": int(score), "components": comps, "weights": weights}
