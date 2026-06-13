# Phase 1: Multi-Tranche Debt & Cash-Sweep Waterfall — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-debt paper LBO with an ordered multi-tranche structure (senior/mezz + revolver) serviced by a real cash-sweep waterfall.

**Architecture:** Tranches are an ordered list in `config.yaml` (index 0 = most senior). `run_lbo` sizes tranches (applying the RBI 75%-of-EV cap proportionally), then runs a yearly loop: accrue cash interest, compute levered FCF, pay mandatory amortization, sweep excess down the priority stack (revolver → senior → mezz), draw the revolver on shortfalls. Exit and IRR math is unchanged (single exit cash flow → closed-form IRR). The sensitivity grid stays 2-D by scaling all tranches proportionally to a target total leverage.

**Tech Stack:** Python 3, pandas, PyYAML, Streamlit; tests via pytest (new) + the existing `smoke_test.py` end-to-end script.

**Spec:** `docs/superpowers/specs/2026-06-13-phase1-lbo-tranches-waterfall-design.md`

---

## File Structure

- **Modify** `config/config.yaml` — `lbo.leverage_multiple`/`lbo.interest_rate` scalars → `lbo.tranches` list + `lbo.revolver_rate`.
- **Modify** `src/lbo_model.py` — rewrite `run_lbo` around tranches + waterfall; add `_size_tranches` helper; update `sensitivity_grid` to scale tranches; rename the `leverage_multiple` override to `total_leverage`.
- **Modify** `src/screener.py:63-64` — `unused_debt_capacity_cr` uses `Σ(tranche turns)` instead of scalar `leverage_multiple`.
- **Modify** `src/app.py` — itemize sources & uses by tranche; show per-tranche ending balances in the schedule.
- **Modify** `smoke_test.py` — update to the new `run_lbo`/`sensitivity_grid` signatures and `sources_uses` shape.
- **Modify** `requirements.txt` — add `pytest>=8.0`.
- **Modify** `README.md` — update "Paper-LBO assumptions" and "Sources & uses" for tranches + waterfall.
- **Create** `tests/conftest.py` — put `src/` on `sys.path` for pytest.
- **Create** `tests/test_lbo_model.py` — engine unit tests (the 7 spec properties minus app-smoke).

---

## Task 1: Test scaffolding (pytest + conftest)

**Files:**
- Create: `tests/conftest.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add pytest to requirements**

Append to `requirements.txt`:
```
pytest>=8.0
```

- [ ] **Step 2: Create conftest to expose `src/` on the path**

`tests/conftest.py`:
```python
import pathlib
import sys

# Make `src/` importable as top-level modules (lbo_model, screener, ...)
SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
```

- [ ] **Step 3: Verify pytest collects nothing yet (no error)**

Run: `python -m pytest tests/ -q`
Expected: `no tests ran` (exit code 5) — confirms collection works and `conftest.py` is valid.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt tests/conftest.py
git commit -m "test: add pytest scaffolding and src path conftest"
```

---

## Task 2: Migrate config to tranches

**Files:**
- Modify: `config/config.yaml`

- [ ] **Step 1: Replace the scalar debt assumptions**

In `config/config.yaml`, replace the `leverage_multiple` and `interest_rate` lines under `lbo:` with a `tranches` list and a `revolver_rate`. The total turns (2.0 + 1.0 = 3.0) match the previous single 3.0x default so sources & uses are unchanged.

```yaml
lbo:
  entry_multiple: 8.0                # EV / LTM EBITDA at entry
  tranches:                          # ordered: index 0 = most senior (swept first)
    - {name: senior,    turns: 2.0, rate: 0.090, mandatory_amort_pct: 0.10}
    - {name: mezzanine, turns: 1.0, rate: 0.130, mandatory_amort_pct: 0.0}
  revolver_rate: 0.085               # interest on drawn revolver balance
  ebitda_growth: 0.08                # annual EBITDA growth over the hold
  hold_years: 5
  tax_rate: 0.25                     # ~Indian corporate rate incl. surcharge
  capex_pct_of_ebitda: 0.25          # maintenance + growth capex assumption
  wc_pct_of_incremental_ebitda: 0.20 # working-capital build per unit of EBITDA growth
```

Leave the `sensitivity:` block unchanged — `leverage_multiples` is now interpreted as *total* leverage targets.

- [ ] **Step 2: Verify YAML parses**

Run: `python -c "import yaml; print(yaml.safe_load(open('config/config.yaml'))['lbo']['tranches'])"`
Expected: a list of two dicts with keys `name, turns, rate, mandatory_amort_pct`.

- [ ] **Step 3: Commit**

```bash
git add config/config.yaml
git commit -m "feat: replace scalar leverage with ordered tranches list in config"
```

> Note: `smoke_test.py` and `app.py` still reference the old API and will be broken between here and Task 8/9. That's expected; the pytest suite (Tasks 3–7) is the source of truth until then.

---

## Task 3: `run_lbo` — single-tranche equivalence (regression guard)

Rewrite `run_lbo` to consume tranches and run the waterfall. This task proves the new engine reduces to the old one for a contrived single-tranche config.

**Files:**
- Modify: `src/lbo_model.py`
- Test: `tests/test_lbo_model.py`

- [ ] **Step 1: Write the failing test**

`tests/test_lbo_model.py`:
```python
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
    # Pre-change model produced MOIC ~2.45x / IRR ~19.6% for these inputs.
    # Assert the closed-form identity and a plausible band rather than a magic number.
    assert 1.0 < res["moic"] < 4.0
    assert abs((1 + res["irr"]) ** 5 - res["moic"]) < 1e-9


def test_sources_equal_uses():
    res = run_lbo(1000.0, base_assumptions())
    su = res["sources_uses"]
    assert abs(su["debt"] + su["sponsor_equity"] - su["enterprise_value"]) < 1e-9
    assert abs(sum(t["amount"] for t in su["tranches"]) - su["debt"]) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lbo_model.py -q`
Expected: FAIL — current `run_lbo` reads `assumptions["leverage_multiple"]`/`["interest_rate"]`, which no longer exist (KeyError), and `sources_uses` has no `tranches` key.

- [ ] **Step 3: Rewrite `run_lbo` and add `_size_tranches`**

Replace the body of `src/lbo_model.py` above `sensitivity_grid` with:
```python
def _size_tranches(entry_ebitda: float, ev: float, tranches: list[dict],
                   total_leverage: float | None) -> tuple[list[dict], float]:
    """Size each tranche in rupees and apply the RBI 75%-of-EV cap.

    If `total_leverage` is given, scale every tranche's turns so they sum to it
    (proportional scaling, used by the sensitivity grid). If the summed debt
    exceeds 0.75 x EV, scale all tranches down by the same factor.
    """
    base_turns = sum(t["turns"] for t in tranches)
    scale = (total_leverage / base_turns) if (total_leverage is not None and base_turns) else 1.0
    sized = [{
        "name": t["name"],
        "rate": t["rate"],
        "mandatory_amort_pct": t.get("mandatory_amort_pct", 0.0),
        "principal": t["turns"] * scale * entry_ebitda,
    } for t in tranches]

    total_debt = sum(t["principal"] for t in sized)
    cap = 0.75 * ev
    if total_debt > cap and total_debt > 0:
        cap_scale = cap / total_debt
        for t in sized:
            t["principal"] *= cap_scale
        total_debt = cap
    return sized, total_debt


def run_lbo(entry_ebitda: float, assumptions: dict,
            entry_multiple: float | None = None,
            total_leverage: float | None = None) -> dict:
    """Run the paper LBO for one company with a multi-tranche waterfall.

    `assumptions` is the `lbo` config section. `entry_multiple` and
    `total_leverage` can be overridden for sensitivity runs; `total_leverage`
    scales all tranches proportionally. Returns sources & uses (itemized by
    tranche), the yearly schedule, and MOIC / IRR.
    """
    a = assumptions
    entry_multiple = entry_multiple if entry_multiple is not None else a["entry_multiple"]
    ev = entry_ebitda * entry_multiple

    sized, total_debt = _size_tranches(entry_ebitda, ev, a["tranches"], total_leverage)
    equity = ev - total_debt

    balances = [t["principal"] for t in sized]
    originals = [t["principal"] for t in sized]
    rates = [t["rate"] for t in sized]
    amort_pcts = [t["mandatory_amort_pct"] for t in sized]
    names = [t["name"] for t in sized]
    revolver = 0.0
    cash = 0.0
    ebitda = entry_ebitda

    rows = []
    for year in range(1, a["hold_years"] + 1):
        prev_ebitda = ebitda
        ebitda = prev_ebitda * (1 + a["ebitda_growth"])

        cash_interest = sum(b * r for b, r in zip(balances, rates)) + revolver * a["revolver_rate"]
        capex = a["capex_pct_of_ebitda"] * ebitda
        taxes = a["tax_rate"] * max(0.0, ebitda - capex - cash_interest)  # capex ~ D&A
        delta_wc = a["wc_pct_of_incremental_ebitda"] * (ebitda - prev_ebitda)
        fcf = ebitda - cash_interest - taxes - capex - delta_wc

        # 1) mandatory amortization (contractual, % of original principal)
        mandatory = []
        for i in range(len(balances)):
            amt = min(amort_pcts[i] * originals[i], balances[i])
            balances[i] -= amt
            mandatory.append(amt)

        # 2) sweep excess down the priority stack, or draw the revolver
        excess = fcf - sum(mandatory)
        sweep = [0.0] * len(balances)
        if excess > 0:
            pay = min(revolver, excess)            # revolver swept first
            revolver -= pay
            excess -= pay
            for i in range(len(balances)):          # then tranches by priority
                pay = min(balances[i], excess)
                balances[i] -= pay
                sweep[i] += pay
                excess -= pay
                if excess <= 1e-12:
                    break
            cash += max(excess, 0.0)                # leftover accumulates
        elif excess < 0:
            revolver += -excess                     # funding gap drawn on revolver

        row = {
            "year": year, "ebitda": ebitda, "interest": cash_interest,
            "taxes": taxes, "capex": capex, "delta_wc": delta_wc,
            "levered_fcf": fcf, "revolver": revolver, "cash": cash,
        }
        for i, nm in enumerate(names):
            row[f"{nm}_repaid"] = mandatory[i] + sweep[i]
            row[f"{nm}_ending"] = balances[i]
        row["ending_debt"] = sum(balances) + revolver
        rows.append(row)

    schedule = pd.DataFrame(rows)
    exit_ev = ebitda * entry_multiple  # flat exit multiple
    ending_debt = sum(balances) + revolver
    exit_equity = exit_ev - ending_debt + cash
    moic = exit_equity / equity if equity > 0 else float("nan")
    irr = moic ** (1 / a["hold_years"]) - 1 if moic > 0 else float("nan")

    return {
        "entry_multiple": entry_multiple,
        "sources_uses": {
            "enterprise_value": ev,
            "debt": total_debt,
            "tranches": [{"name": t["name"], "amount": t["principal"],
                          "pct_of_ev": t["principal"] / ev} for t in sized],
            "sponsor_equity": equity,
            "debt_pct_of_ev": total_debt / ev,
        },
        "schedule": schedule,
        "exit_ev": exit_ev,
        "exit_net_debt": ending_debt - cash,
        "exit_equity": exit_equity,
        "moic": moic,
        "irr": irr,
    }
```
Keep the existing `import pandas as pd` at the top of the file.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lbo_model.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lbo_model.py tests/test_lbo_model.py
git commit -m "feat: multi-tranche run_lbo with cash-sweep waterfall"
```

---

## Task 4: Priority invariant — senior repaid before mezz principal moves

**Files:**
- Test: `tests/test_lbo_model.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lbo_model.py`:
```python
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
```

- [ ] **Step 2: Run to verify it passes (guard test)**

Run: `python -m pytest tests/test_lbo_model.py::test_mezz_principal_untouched_by_sweep_while_senior_outstanding -q`
Expected: PASS — the priority loop in `run_lbo` only reaches mezz (index 1) after senior (index 0) hits zero.

> This is a property already guaranteed by Task 3's implementation; the test pins the invariant so a future refactor can't silently break sweep ordering. If it FAILS, the sweep loop order is wrong — fix `run_lbo`, do not weaken the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_lbo_model.py
git commit -m "test: pin sweep priority invariant (senior before mezz)"
```

---

## Task 5: Mandatory amortization behaviour

**Files:**
- Test: `tests/test_lbo_model.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lbo_model.py`:
```python
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
```

- [ ] **Step 2: Run to verify it passes**

Run: `python -m pytest tests/test_lbo_model.py::test_senior_mandatory_amortization_each_year -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_lbo_model.py
git commit -m "test: senior repays at least scheduled mandatory amort each year"
```

---

## Task 6: RBI 75% cap with proportional tranche scaling

**Files:**
- Test: `tests/test_lbo_model.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lbo_model.py`:
```python
def test_rbi_cap_binds_and_scales_tranches_proportionally():
    # Low entry multiple + high leverage forces the 0.75 x EV cap to bind.
    a = base_assumptions()
    res = run_lbo(1000.0, a, entry_multiple=4.0, total_leverage=3.5)
    ev = 4000.0
    su = res["sources_uses"]
    assert abs(su["debt"] - 0.75 * ev) < 1e-9          # total capped at 75% of EV
    # Pre-cap turns were senior:mezz = 2.0:1.0 scaled to 3.5 total; the cap
    # scales both by the same factor, so the 2:1 ratio is preserved.
    senior = next(t for t in su["tranches"] if t["name"] == "senior")
    mezz = next(t for t in su["tranches"] if t["name"] == "mezzanine")
    assert abs(senior["amount"] / mezz["amount"] - 2.0) < 1e-9


def test_cap_does_not_bind_when_leverage_modest():
    res = run_lbo(1000.0, base_assumptions())          # 3.0x on 8.0x EV = 37.5%
    su = res["sources_uses"]
    assert abs(su["debt"] - 3000.0) < 1e-9
```

- [ ] **Step 2: Run to verify it passes**

Run: `python -m pytest tests/test_lbo_model.py -k "rbi_cap or cap_does_not" -q`
Expected: PASS (2 tests) — `_size_tranches` applies the cap factor uniformly.

- [ ] **Step 3: Commit**

```bash
git add tests/test_lbo_model.py
git commit -m "test: RBI cap binds and scales tranches proportionally"
```

---

## Task 7: `sensitivity_grid` — proportional scaling to total leverage

**Files:**
- Modify: `src/lbo_model.py` (`sensitivity_grid`)
- Test: `tests/test_lbo_model.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lbo_model.py`:
```python
from lbo_model import sensitivity_grid


def test_grid_center_cell_matches_base_run():
    a = base_assumptions()
    base = run_lbo(1000.0, a)                          # base turns sum to 3.0
    irr, moic = sensitivity_grid(1000.0, a,
                                 entry_multiples=[6.0, 8.0, 10.0],
                                 leverage_multiples=[2.0, 3.0, 4.0])
    # Cell at entry 8.0 / total leverage 3.0 == the unscaled base run.
    assert abs(irr.loc[8.0, 3.0] - base["irr"]) < 1e-12
    assert abs(moic.loc[8.0, 3.0] - base["moic"]) < 1e-12


def test_grid_high_leverage_cell_triggers_cap():
    a = base_assumptions()
    irr, moic = sensitivity_grid(1000.0, a,
                                 entry_multiples=[4.0],
                                 leverage_multiples=[3.5])
    # 3.5x on a 4.0x EV would be 87.5% > 75%; cap binds but run still returns a number.
    import math
    assert not math.isnan(moic.loc[4.0, 3.5])
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_lbo_model.py -k grid -q`
Expected: FAIL — current `sensitivity_grid` calls `run_lbo(..., leverage_multiple=lm)`, but the override is now named `total_leverage`.

- [ ] **Step 3: Update `sensitivity_grid`**

In `src/lbo_model.py`, change the inner call so the leverage axis maps to `total_leverage`:
```python
def sensitivity_grid(entry_ebitda: float, assumptions: dict,
                     entry_multiples: list[float],
                     leverage_multiples: list[float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """IRR and MOIC grids across entry multiple (rows) x total leverage (cols).

    Each column scales all tranches proportionally to the target total leverage.
    """
    irr = pd.DataFrame(index=entry_multiples, columns=leverage_multiples, dtype=float)
    moic = irr.copy()
    for em in entry_multiples:
        for lm in leverage_multiples:
            result = run_lbo(entry_ebitda, assumptions,
                             entry_multiple=em, total_leverage=lm)
            irr.loc[em, lm] = result["irr"]
            moic.loc[em, lm] = result["moic"]
    irr.index.name = "entry_multiple"
    irr.columns.name = "total_leverage"
    moic.index.name = "entry_multiple"
    moic.columns.name = "total_leverage"
    return irr, moic
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_lbo_model.py -k grid -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full engine suite**

Run: `python -m pytest tests/test_lbo_model.py -q`
Expected: PASS (all tests from Tasks 3–7).

- [ ] **Step 6: Commit**

```bash
git add src/lbo_model.py tests/test_lbo_model.py
git commit -m "feat: sensitivity grid scales tranches to target total leverage"
```

---

## Task 8: Screener — `unused_debt_capacity` from summed turns

**Files:**
- Modify: `src/screener.py:62-64`

- [ ] **Step 1: Update the metric**

In `compute_metrics` (`src/screener.py`), replace the `unused_debt_capacity_cr` computation that uses `lbo["leverage_multiple"]` with the sum of tranche turns:
```python
            # Headroom to the modelled LBO leverage level — the thesis metric.
            "unused_debt_capacity_cr": max(
                0.0, sum(t["turns"] for t in lbo["tranches"]) * ebitda - net_debt),
```
The surrounding `lbo = cfg["lbo"]` lookup already exists at the top of `compute_metrics`; no other change needed.

- [ ] **Step 2: Verify the screener still computes**

Run:
```bash
python -c "import sys; sys.path.insert(0,'src'); import pandas as pd; from data_loader import load_config, load_fundamentals; from screener import compute_metrics; cfg=load_config(); f=load_fundamentals(); mk=pd.DataFrame({'ticker':['INFY.NS','TCS.NS'],'market_cap_cr':[660000.0,None]}); print(compute_metrics(f,mk,cfg)[['ticker','unused_debt_capacity_cr']].to_string(index=False))"
```
Expected: prints two rows with numeric `unused_debt_capacity_cr` (no KeyError on `leverage_multiple`).

- [ ] **Step 3: Commit**

```bash
git add src/screener.py
git commit -m "feat: unused debt capacity uses summed tranche turns"
```

---

## Task 9: App — itemize sources & uses and per-tranche schedule

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Read the current tear-sheet rendering**

Open `src/app.py` and locate where `run_lbo` results are displayed: the sources & uses block (reads `sources_uses["debt"]`, `["sponsor_equity"]`, etc.) and the schedule table (`res["schedule"]`), plus any `leverage_multiple` slider/reference.

- [ ] **Step 2: Update sources & uses to itemize tranches**

Where the sources & uses are shown, render one row per tranche from `su["tranches"]` (each has `name`, `amount`, `pct_of_ev`) followed by the `sponsor_equity` and `enterprise_value` totals. Keep using `su["debt"]` for the total debt figure. Example pattern (adapt to the existing Streamlit layout):
```python
su = res["sources_uses"]
su_rows = [{"item": t["name"], "₹cr": t["amount"], "% of EV": t["pct_of_ev"]}
           for t in su["tranches"]]
su_rows.append({"item": "sponsor equity", "₹cr": su["sponsor_equity"],
                "% of EV": su["sponsor_equity"] / su["enterprise_value"]})
st.dataframe(pd.DataFrame(su_rows), hide_index=True)
```

- [ ] **Step 3: Update the schedule display**

The schedule now has per-tranche `<name>_ending` / `<name>_repaid` columns plus `revolver`, `cash`, and total `ending_debt`. Show the schedule as-is (`st.dataframe(res["schedule"])`) or select a readable column subset. Remove any reference to a single `leverage_multiple` slider; if a leverage control is desired, bind it to `total_leverage` (pass to `run_lbo(..., total_leverage=...)`).

- [ ] **Step 4: Smoke-test both views render via AppTest**

Run:
```bash
python -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('src/app.py', default_timeout=60).run(); assert not at.exception, at.exception; print('app OK')"
```
Expected: prints `app OK` with no exception. If a control changed, exercise it (set the relevant widget and `.run()` again) before asserting.

- [ ] **Step 5: Commit**

```bash
git add src/app.py
git commit -m "feat: itemize tranches in sources & uses and schedule on tear sheet"
```

---

## Task 10: Update `smoke_test.py` end-to-end script

**Files:**
- Modify: `smoke_test.py`

- [ ] **Step 1: Update the LBO assertions to the new API**

In `smoke_test.py`, the `run_lbo`/`sensitivity_grid` calls and `sources_uses` checks need updating:
- `run_lbo(1000.0, cfg["lbo"])` — unchanged call; `su["debt"]` is still 3000 and `sponsor_equity` 5000 for the default (2.0x + 1.0x), so those asserts hold.
- Replace the cap check `run_lbo(..., leverage_multiple=3.5)` with `run_lbo(1000.0, cfg["lbo"], entry_multiple=4.0, total_leverage=3.5)` and keep `assert abs(capped["sources_uses"]["debt"] - 0.75 * 4000) < 1e-9`.
- The center-cell check `irr_g.loc[8.0, 3.0]` still works (leverage 3.0 == base). Keep it.
- `res["schedule"]["ending_debt"].is_monotonic_decreasing` still holds (positive FCF, no revolver draw). Keep it.

- [ ] **Step 2: Run the end-to-end script**

Run: `python smoke_test.py`
Expected: prints the universe/metrics/rationale, the LBO line, the IRR grid, and `All assertions passed.` with no traceback.

- [ ] **Step 3: Run the full pytest suite too**

Run: `python -m pytest tests/ -q`
Expected: PASS (all engine tests).

- [ ] **Step 4: Commit**

```bash
git add smoke_test.py
git commit -m "test: update end-to-end smoke test for tranche API"
```

---

## Task 11: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite the "Paper-LBO assumptions" and "Sources & uses" sections**

Update the README to describe: the ordered tranche list (senior/mezz + revolver) and what each field means; the waterfall (mandatory amort first, then sweep down the priority stack, revolver on shortfalls); that the RBI 75%-of-EV cap now applies to total debt and scales tranches proportionally; and that the sensitivity grid's leverage axis is now *total* leverage with proportional scaling. Note in "Limitations" that fees, management rollover, and PIK remain out of scope (Phase 1), and that a three-statement build is planned (Phase 2).

- [ ] **Step 2: Sanity-check the doc**

Run: `python -c "print(open('README.md').read()[:200])"`
Expected: README opens; skim that the LBO section now mentions tranches and the waterfall.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: describe multi-tranche debt and cash-sweep waterfall"
```

---

## Done criteria

- `python -m pytest tests/ -q` — all engine tests pass.
- `python smoke_test.py` — prints `All assertions passed.`
- `python -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('src/app.py').run(); assert not at.exception"` — app renders.
- Default config (2.0x senior + 1.0x mezz) keeps total entry debt at 3.0x EBITDA; returns differ from the old single-3.0x-at-9.5% model because of the mezz tranche — this is expected and documented.
