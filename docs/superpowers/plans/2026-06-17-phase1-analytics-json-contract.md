# Phase 1 — Analytics Layer + JSON Contract — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `src/analytics.py` (advanced-quant functions that only call the existing `run_lbo`) and `tools/export_data.py` (orchestrator that screens, runs every analytic per passer, and writes one JSON-safe `results.json`) — the data contract the Next.js frontend (Phase 2/3) will read.

**Architecture:** All math runs in Python at export time. `analytics.py` imports `run_lbo`/`sensitivity_grid_premium` from `src/lbo_model.py` and the screener from `src/screener.py` — **no existing model math is modified**. `export_data.py` reuses `tools/export_site.py::gather` for the screen, calls `analytics.build_results`, sanitizes NaN/inf → `null`, and serializes to `web-app/public/data/results.json`.

**Tech Stack:** Python 3.14, pandas, numpy, SALib (Sobol), pytest. Tests import `src/` modules directly via `tests/conftest.py` (already on `sys.path`).

---

## Reference: the building blocks this plan stands on

- `run_lbo(entry_revenue, entry_ebitda, assumptions, entry_multiple=None, total_leverage=None, entry_ev=None, exit_multiple=None) -> dict` — returns `irr`, `moic`, `exit_equity`, `exit_net_debt`, `exit_ev`, `sources_uses` (with `sponsor_equity`, `enterprise_value`, `debt`), `schedule` (DataFrame with per-year `ebitda`, `interest`, `ending_debt`, `cash`), `income_statement`, `cash_flow`, `balance_sheet`, `entry_multiple`, `exit_multiple`, `max_balance_error`.
- Take-private entry price: `entry_ev = market_cap_cr * (1 + premium_pct/100) + net_debt_cr` (see `tools/export_site.py:171`).
- Screener row columns (from `src/screener.py::compute_metrics`): `ticker`, `revenue_cr`, `ebitda_cr`, `ebitda_margin`, `net_debt_cr`, `net_debt_to_ebitda`, `interest_coverage`, `fcf_cr`, `fcf_yield`, `promoter_holding_pct`, `promoter_pledge_pct`, `market_cap_cr`, `unused_debt_capacity_cr`, `latest_year`.
- Config: `cfg["lbo"]` is the assumptions dict `run_lbo` takes; `cfg["lbo"]["control_premium_pct"]` (25.0), tranche `turns` sum = base leverage; `cfg["screening"]["min_interest_coverage"]` (3.0); `cfg["sensitivity"]` axes.
- `tools/export_site.py::gather(no_fetch)` returns **`(cfg, universe, results)`** in that order (a 3-tuple; `results` is the screened DataFrame). It does **not** return a date — the as-of date is `datetime.date.today().isoformat()` (computed in `export_site.main`). Unpack as `cfg, _universe, results_df = gather(no_fetch)` and source the date separately.

## Frozen decisions for Phase 1 (the "freeze before tests" items from the spec)

- **Return hurdle:** `HURDLE_IRR = 0.20` — module constant in `analytics.py` (matches the static site's 20% PE hurdle). Configurable later; pinned now so tests are deterministic.
- **Monte Carlo / Sobol input distributions** (independent draws, indicative — stated on the tear sheet later):
  - `revenue_growth ~ Normal(mean=base_growth, sd=0.03)`, clipped to `[0.0, 2*base_growth]`
  - `ebitda_shock ~ Normal(mean=1.0, sd=0.05)` (multiplies `entry_ebitda`; a margin shock), clipped to `[0.7, 1.3]`
  - `exit_multiple ~ Normal(mean=entry_multiple, sd=1.0)`, clipped to `[entry_multiple-3, entry_multiple+3]`, floored at 1.0
  - `MC_N = 5000`, `SEED = 42`. Sobol uses SALib Saltelli with `SOBOL_N = 1024` base samples.
- **Canonical JSON key set** is frozen in Task 11 (`COMPANY_KEYS`), single source of truth so exporter and frontend can't drift.

## File structure

- **Create** `src/analytics.py` — all advanced-quant functions + assembly. Single module per the spec's "one new file." (If it exceeds ~450 lines during build, split into a `src/analytics/` package by responsibility — inputs / montecarlo / bridges / solvers / sensitivity / india / assemble — re-exported from `__init__`. Default: single module.)
- **Create** `tools/export_data.py` — CLI orchestrator.
- **Create** `tests/test_analytics.py` — unit + parity tests.
- **Modify** `requirements-dev.txt` — add `SALib>=1.4` (CI/export only; not a Streamlit runtime dep).
- **Output (generated, git-ignored until Phase 2 wires the frontend):** `web-app/public/data/results.json`.

---

### Task 0: Dependency + test scaffolding

**Files:**
- Modify: `requirements-dev.txt`
- Create: `tests/test_analytics.py`

- [ ] **Step 1: Add SALib to dev deps**

In `requirements-dev.txt`, after the `Jinja2` line add:

```
SALib>=1.4      # Sobol global-sensitivity indices for tools/export_data.py
```

- [ ] **Step 2: Install**

Run: `pip install -r requirements-dev.txt`
Expected: SALib (and scipy) installed, no errors.

- [ ] **Step 3: Create the test module with shared fixtures**

```python
# tests/test_analytics.py
import math
import pandas as pd
import pytest

import analytics
from data_loader import load_config  # if present; else build cfg inline below


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
```

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt tests/test_analytics.py
git commit -m "test: scaffold analytics tests + add SALib dev dep"
```

---

### Task 1: `company_inputs` — adapter from a screener row to LBO inputs

Every analytic needs the same derived inputs. Centralize the extraction once.

**Files:**
- Create: `src/analytics.py`
- Test: `tests/test_analytics.py`

- [ ] **Step 1: Write the failing test**

```python
def test_company_inputs_prices_take_private_ev():
    inp = analytics.company_inputs(sample_row(), base_cfg())
    # entry_ev = market_cap*(1+prem) + net_debt = 9000*1.25 + 500 = 11750
    assert inp["entry_ev"] == pytest.approx(11750.0)
    assert inp["entry_revenue"] == 5000.0
    assert inp["entry_ebitda"] == 1000.0
    assert inp["total_leverage"] == pytest.approx(3.0)   # 2.0 + 1.0 turns
    assert inp["premium_pct"] == 25.0
    assert inp["assumptions"] is base_cfg()["lbo"] or "tranches" in inp["assumptions"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analytics.py::test_company_inputs_prices_take_private_ev -v`
Expected: FAIL — `AttributeError: module 'analytics' has no attribute 'company_inputs'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/analytics.py
"""Advanced-quant layer for the LBO showcase.

Every function here only *calls* run_lbo (and the screener); none of the
existing model math is modified. Pure and import-safe (no Streamlit), so the
exporter and pytest can import it freely.
"""
from __future__ import annotations

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analytics.py::test_company_inputs_prices_take_private_ev -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): company_inputs adapter (row -> take-private LBO inputs)"
```

---

### Task 2: `monte_carlo` + `downside_risk`

**Files:**
- Modify: `src/analytics.py`
- Test: `tests/test_analytics.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_analytics.py -k "monte_carlo or downside" -v`
Expected: FAIL — functions not defined.

- [ ] **Step 3: Implement**

```python
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
```

Add `import math` at the top of `src/analytics.py`.

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/test_analytics.py -k "monte_carlo or downside" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): monte_carlo + downside_risk (P-loss, VaR, CVaR)"
```

---

### Task 3: `irr_bridge` + `value_bridge`

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing tests**

```python
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
```

- [ ] **Step 2: Run — expect FAIL.**
Run: `pytest tests/test_analytics.py -k bridge -v`

- [ ] **Step 3: Implement**

```python
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
```

> Implementation note: `fees_and_other` is the reconciling residual — the test asserts the decomposition is exact by construction. If `entry_net_debt` derivation reads awkwardly, compute it directly as `inp["entry_ev"] - entry_equity` (entry EV funded by sponsor equity + entry net debt + fees); keep the residual line so the identity holds.

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): irr_bridge + value_bridge decompositions`

---

### Task 4: `max_bid_solver` (inverse model — highest premium that clears the hurdle)

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing tests**

```python
def test_max_bid_lands_on_hurdle():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    sol = analytics.max_bid_solver(inp, target_irr=0.20)
    assert sol["converged"]
    # re-price at the solved premium and confirm IRR ~ target
    ev = inp["market_cap"] * (1 + sol["max_premium_pct"] / 100.0) + inp["net_debt"]
    irr = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                  entry_ev=ev, total_leverage=inp["total_leverage"])["irr"]
    assert irr == pytest.approx(0.20, abs=2e-3)

def test_max_bid_no_solution_when_unaffordable():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    sol = analytics.max_bid_solver(inp, target_irr=0.99)  # impossible hurdle
    assert sol["converged"] is False
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement (bisection; IRR is decreasing in premium)**

```python
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
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): max_bid_solver (max premium for target IRR)`

---

### Task 5: `debt_capacity_solver` (max leverage that holds the coverage covenant)

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
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
```

> Note: `_min_coverage` guards zero-interest years with `.replace(0, np.nan)` then `.min()`. The `converged` path assumes at least one finite coverage value exists; if a row produced all-zero/non-positive interest, `min` would be NaN and the bisection would silently collapse to `lo`. Healthy passers are fine — but if you add a degenerate test row, assert this solver returns `converged: False` rather than a bogus leverage.

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): debt_capacity_solver (max leverage under coverage covenant)`

---

### Task 6: `optimal_exit` (IRR-maximizing hold year)

Resolves the spec's feasibility question: `run_lbo` honours `assumptions["hold_years"]`, so exit at year *k* = run with `hold_years=k`. No engine change.

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing test**

```python
def test_optimal_exit_within_range():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    sol = analytics.optimal_exit(inp)
    years = [r["year"] for r in sol["by_year"]]
    assert years == [1, 2, 3, 4, 5]
    assert 1 <= sol["best_year"] <= 5
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): optimal_exit (IRR by hold year)`

---

### Task 7: `sobol_indices` (global variance-based sensitivity)

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing test**

```python
def test_sobol_indices_keys_and_ranges():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    s = analytics.sobol_indices(inp, n=256)   # small N for test speed
    for k in ("revenue_growth", "ebitda_shock", "exit_multiple"):
        assert k in s["total_order"] and k in s["first_order"]
    # total-order >= first-order (within numerical noise) for each driver
    for k in s["first_order"]:
        assert s["total_order"][k] >= s["first_order"][k] - 0.05
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement (SALib Saltelli + Sobol)**

```python
from SALib.sample import saltelli
from SALib.analyze import sobol as sobol_analyze


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
```

- [ ] **Step 4: Run — expect PASS** (allow a few seconds).
- [ ] **Step 5: Commit** `feat(analytics): sobol_indices (global sensitivity via SALib)`

---

### Task 8: `iso_irr_frontier` (the target-IRR decision boundary)

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing test**

```python
def test_iso_frontier_points_hit_target():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    fr = analytics.iso_irr_frontier(inp, target_irr=0.20)
    assert fr["target_irr"] == 0.20
    for pt in fr["points"]:
        ev = inp["market_cap"] * (1 + pt["premium_pct"] / 100.0) + inp["net_debt"]
        irr = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                      entry_ev=ev, total_leverage=inp["total_leverage"],
                      exit_multiple=pt["exit_multiple"])["irr"]
        assert irr == pytest.approx(0.20, abs=5e-3)
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement (for each exit multiple, bisect the premium that hits target)**

```python
def iso_irr_frontier(inp: dict, target_irr: float = HURDLE_IRR,
                     exit_multiples: list[float] | None = None) -> dict:
    em = _entry_multiple(inp)
    if exit_multiples is None:
        exit_multiples = [round(em - 2 + i, 1) for i in range(5)]  # em-2 .. em+2
    points = []
    for xm in exit_multiples:
        lo, hi = 0.0, 100.0
        def irr_at(p):
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
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): iso_irr_frontier (target-IRR decision boundary)`

---

### Task 9: `feasibility_score` (India take-private composite)

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing tests**

```python
def test_feasibility_score_range_and_pledge_monotonicity():
    cfg = base_cfg(); row = sample_row()
    s_low_pledge = analytics.feasibility_score(row, cfg)
    high = row.copy(); high["promoter_pledge_pct"] = 20.0
    s_high_pledge = analytics.feasibility_score(high, cfg)
    assert 0 <= s_low_pledge["score"] <= 100
    assert s_high_pledge["score"] < s_low_pledge["score"]   # more pledge -> less feasible
    assert set(s_low_pledge["components"]) >= {"holding", "pledge", "float", "valuation"}
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement (transparent weighted sub-scores, each 0–100)**

```python
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
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): feasibility_score (India take-private composite)`

---

### Task 10: `delisting_model` (indicative reverse-book-building structure)

Clearly indicative — uses only available inputs (no shareholding distribution). States its own assumptions so the UI can label it.

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing test**

```python
def test_delisting_model_structure():
    cfg = base_cfg(); row = sample_row()
    inp = analytics.company_inputs(row, cfg)
    d = analytics.delisting_model(inp, row, cfg)
    assert d["acceptance_threshold_pct"] == 90.0
    # public float that must tender = 90 - promoter_holding
    assert d["float_to_tender_pct"] == pytest.approx(90.0 - 62.0)
    assert d["indicative"] is True
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
def delisting_model(inp: dict, row: pd.Series, cfg: dict) -> dict:
    """Indicative SEBI reverse-book-building structure (NOT a price prediction)."""
    holding = float(row.get("promoter_holding_pct") or 0.0)
    threshold = 90.0
    indicative_premium = inp["premium_pct"]
    discovered_ev = inp["market_cap"] * (1 + indicative_premium / 100.0) + inp["net_debt"]
    return {
        "indicative": True,
        "acceptance_threshold_pct": threshold,
        "promoter_holding_pct": holding,
        "float_to_tender_pct": max(0.0, threshold - holding),
        "indicative_premium_pct": indicative_premium,
        "indicative_discovered_ev_cr": discovered_ev,
        "assumptions": "Premium = config control_premium_pct; assumes full tender of "
                       "required float at the discovered price. Illustrative only.",
    }
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): delisting_model (indicative reverse-book-building)`

---

### Task 11: `build_company_block` — assemble one passer + freeze the canonical keys

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing test**

```python
def test_company_block_has_canonical_keys():
    cfg = base_cfg(); row = sample_row()
    block = analytics.build_company_block(row, cfg)
    assert set(block) == set(analytics.COMPANY_KEYS)
    assert block["returns"]["irr"] is not None
    assert "income" in block["statements"]
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
COMPANY_KEYS = ["ticker", "name", "statements", "debt_schedule", "sources_uses",
                "returns", "montecarlo", "downside", "sensitivity", "solvers",
                "sobol", "feasibility", "delisting"]


def build_company_block(row: pd.Series, cfg: dict) -> dict:
    inp = company_inputs(row, cfg)
    res = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                  entry_ev=inp["entry_ev"], total_leverage=inp["total_leverage"])
    mc = monte_carlo(inp)
    return {
        "ticker": row["ticker"],
        # screener rows carry no display name; derive it like export_site.py / returns.py
        "name": str(row["ticker"]).replace(".NS", ""),
        "statements": {"income": res["income_statement"].to_dict("records"),
                       "cash_flow": res["cash_flow"].to_dict("records"),
                       "balance_sheet": res["balance_sheet"].to_dict("records")},
        "debt_schedule": res["schedule"].to_dict("records"),
        "sources_uses": res["sources_uses"],
        "returns": {"irr": res["irr"], "moic": res["moic"],
                    "irr_bridge": irr_bridge(inp), "value_bridge": value_bridge(inp)},
        "montecarlo": mc,
        "downside": downside_risk(mc),
        "sensitivity": {"iso_frontier": iso_irr_frontier(inp)},
        "solvers": {"max_bid": max_bid_solver(inp),
                    "debt_capacity": debt_capacity_solver(
                        inp, cfg["screening"]["min_interest_coverage"]),
                    "optimal_exit": optimal_exit(inp)},
        "sobol": sobol_indices(inp),
        "feasibility": feasibility_score(row, cfg),
        "delisting": delisting_model(inp, row, cfg),
    }
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): build_company_block + frozen COMPANY_KEYS contract`

---

### Task 12: `build_results` + JSON-safe serialization

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing tests**

```python
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
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
def _json_safe(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        v = float(obj); return v if math.isfinite(v) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


def build_results(results_df: pd.DataFrame, cfg: dict, as_of: str) -> dict:
    passed = results_df[results_df["passes_screen"]]   # apply_screen sets this bool col
    companies, passers = {}, []
    for _, row in passed.iterrows():
        block = build_company_block(row, cfg)
        companies[row["ticker"]] = block
        passers.append({"ticker": row["ticker"], "name": block["name"],
                        "irr": block["returns"]["irr"], "moic": block["returns"]["moic"],
                        "feasibility": block["feasibility"]["score"],
                        "max_bid_premium_pct": block["solvers"]["max_bid"].get("max_premium_pct")})
    payload = {"as_of": as_of,
               "config": {"hurdle_irr": HURDLE_IRR, "hold_years": cfg["lbo"]["hold_years"],
                          "control_premium_pct": cfg["lbo"]["control_premium_pct"]},
               "universe": {"screened": int(len(results_df)), "passed": int(len(passed))},
               "passers": passers, "companies": companies}
    return _json_safe(payload)
```

> Note 1 — pass column (confirmed): `apply_screen` (src/screener.py) sets a boolean `passes_screen` column (= all `pass_*` criteria true, NaN treated as fail). The filter above is correct as written.
>
> Note 2 — degenerate passers: `run_lbo` returns `float("nan")` for `irr`/`moic` on a negative-equity / negative-EV name (the JUSTDIAL case the repo already fixed). For such a row, `irr_bridge`/`value_bridge` components and the `passers[]` IRR will be NaN; `_json_safe` converts every NaN to `null`, so the JSON stays valid (Task 12's "no NaN tokens" assertion still holds) and the frontend renders "—". Add one degenerate row to the suite to lock this in: a `sample_row()` copy with `market_cap_cr` tiny enough that sponsor equity goes non-positive, asserting `build_company_block` returns and `json.dumps` succeeds with `returns.irr is None`.

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): build_results with JSON-safe serialization`

---

### Task 13: `tools/export_data.py` CLI

**Files:** Create `tools/export_data.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Failing test**

```python
def test_export_data_writes_valid_json(tmp_path):
    import sys, pathlib, json, subprocess
    out = tmp_path / "results.json"
    root = pathlib.Path(__file__).resolve().parent.parent
    subprocess.run([sys.executable, str(root / "tools" / "export_data.py"),
                    "--no-fetch", "--out", str(out)], check=True, cwd=root)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "passers" in data and "companies" in data and data["as_of"]
```

- [ ] **Step 2: Run — expect FAIL** (file not created / script missing).

- [ ] **Step 3: Implement**

```python
# tools/export_data.py
"""Build results.json: screen the universe, run every analytic per passer.

Usage:
  python tools/export_data.py                 # live yfinance fetch
  python tools/export_data.py --no-fetch      # use data/market_snapshot.csv
  python tools/export_data.py --out path.json # custom output path
"""
import argparse, json, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import analytics
from export_site import gather


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "web-app" / "public" / "data" / "results.json"))
    args = ap.parse_args(argv)

    cfg, _universe, results_df = gather(no_fetch=args.no_fetch)  # (cfg, universe, results)
    as_of = date.today().isoformat()
    payload = analytics.build_results(results_df, cfg, as_of)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out} — {payload['universe']['passed']} passers "
          f"of {payload['universe']['screened']} screened (as of {payload['as_of']}).")


if __name__ == "__main__":
    main()
```

> Windows console note: keep `print()` ASCII-only (the repo already hit a cp1252 crash on a `→` arrow — see commit a085a87). No non-ASCII in stdout.

- [ ] **Step 4: Run — expect PASS.** Also run it for real once:
Run: `python tools/export_data.py --no-fetch`
Expected: writes `web-app/public/data/results.json`, prints the passer count.

- [ ] **Step 5: Commit** `feat: tools/export_data.py — emit results.json contract`

---

### Task 14: Full-suite green + gitignore the generated artifact

**Files:** Modify `.gitignore`; run the whole suite.

- [ ] **Step 1: Ignore the generated JSON** (Phase 2 decides whether to commit it; for now it's a build artifact)

Append to `.gitignore`:

```
# generated data contract (rebuilt by tools/export_data.py / weekly CI)
web-app/public/data/results.json
```

- [ ] **Step 2: Run the full analytics suite**

Run: `pytest tests/test_analytics.py -v`
Expected: all PASS.

- [ ] **Step 3: Run the entire repo suite (no regressions in existing tests)**

Run: `pytest -q`
Expected: all PASS (existing `test_lbo_model.py`, `test_statements.py`, `test_export_site.py` unaffected — no `src/` math changed).

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore generated results.json build artifact"
```

---

## Done criteria for Phase 1

- `pytest -q` green, including all of `tests/test_analytics.py`.
- `python tools/export_data.py --no-fetch` writes a `results.json` whose `passers` keys exactly match `companies`, with no `NaN`/`Infinity` tokens.
- No file under `src/` other than the new `src/analytics.py` is modified.
- Canonical keys live only in `analytics.COMPANY_KEYS` (the contract Phase 2/3 codes against).

## Hand-off to Phase 2

Phase 2 (dashboard) and Phase 3 (tear sheet) are separate plans. They consume `web-app/public/data/results.json`. The frozen `COMPANY_KEYS` + the `passers[]` summary shape are the interface; the Next.js app should type that contract (e.g. a generated `types.ts`) so a schema change in Python surfaces as a TypeScript error.
