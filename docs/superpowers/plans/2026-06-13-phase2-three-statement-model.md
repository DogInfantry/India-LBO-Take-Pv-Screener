# Phase 2: Three-Statement Articulation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build articulating Income Statement, Balance Sheet, and Cash Flow Statement on top of Phase 1's multi-tranche waterfall, with the balance sheet balancing every year as the integrity check.

**Architecture:** A new pure-function module `src/statements.py` holds the opening balance sheet and income-statement helpers. `run_lbo` in `src/lbo_model.py` becomes revenue-driven and orchestrates one yearly loop where the income statement, the existing debt waterfall, the cash flow statement, and the balance sheet interlock. Interest accrues on opening balances so the loop is a single forward pass (no circularity); the balance sheet balances by construction, so the balance check is a bug detector.

**Tech Stack:** Python 3, pandas, PyYAML, Streamlit; pytest + the existing `smoke_test.py`.

**Spec:** `docs/superpowers/specs/2026-06-13-phase2-three-statement-model-design.md`

---

## File Structure

- **Modify** `config/config.yaml` — under `lbo:` remove `ebitda_growth`, `capex_pct_of_ebitda`, `wc_pct_of_incremental_ebitda`; add `revenue_growth`, `ppe_pct_of_revenue`, `nwc_pct_of_revenue`, `da_pct_of_ppe`, `capex_pct_of_revenue`.
- **Create** `src/statements.py` — pure helpers: `opening_balance_sheet`, `income_statement_row`.
- **Modify** `src/lbo_model.py` — `run_lbo` signature gains `entry_revenue`; yearly loop rewritten as a three-statement build; return dict gains `income_statement`, `cash_flow`, `balance_sheet`, `max_balance_error`, `margin`. `_size_tranches`, the waterfall mechanism, and `sensitivity_grid` structure are preserved (the latter gains `entry_revenue`). Update the module docstring.
- **Modify** `tests/test_lbo_model.py` — migrate `base_assumptions()` to the new config keys; pass `entry_revenue` in all `run_lbo`/`sensitivity_grid` calls; retire `legacy_single_tranche()` + `test_single_tranche_reproduces_legacy_numbers`.
- **Create** `tests/test_statements.py` — integrity tests (BS balances yearly, opening BS balances, CFS cash reconciles, IS ties, PP&E roll, retained earnings, goodwill flat).
- **Modify** `src/app.py` — pass `entry_revenue`; add IS/BS/CFS views + a "balance sheet ties ✓" indicator; update the schedule rename (`delta_wc`→`delta_nwc`, `levered_fcf`→`fcf_for_debt`).
- **Modify** `smoke_test.py` — new `run_lbo` signature; exercise the three statements + balance check.
- **Modify** `README.md` — describe the three-statement build, the revenue driver, and goodwill-as-plug; note it is assumption-driven, not real PPA.

> `src/screener.py` is unchanged — `unused_debt_capacity_cr` uses tranche turns, untouched by Phase 2.

---

## Task 1: Config — revenue-driven ratios

**Files:**
- Modify: `config/config.yaml`

- [ ] **Step 1: Swap the operating ratios**

In `config/config.yaml`, under `lbo:`, REMOVE `ebitda_growth`, `capex_pct_of_ebitda`, and `wc_pct_of_incremental_ebitda`. Keep `entry_multiple`, `tranches`, `revolver_rate`, `hold_years`, `tax_rate`. ADD the revenue-driven ratios so the `lbo:` block reads:

```yaml
lbo:
  entry_multiple: 8.0                # EV / LTM EBITDA at entry
  tranches:                          # ordered: index 0 = most senior (swept first)
    - {name: senior,    turns: 2.0, rate: 0.090, mandatory_amort_pct: 0.10}
    - {name: mezzanine, turns: 1.0, rate: 0.130, mandatory_amort_pct: 0.0}
  revolver_rate: 0.085               # interest on drawn revolver balance
  hold_years: 5
  tax_rate: 0.25                     # ~Indian corporate rate incl. surcharge
  revenue_growth: 0.08               # annual revenue growth (margin held flat)
  ppe_pct_of_revenue: 0.40           # opening PP&E as a share of entry revenue
  nwc_pct_of_revenue: 0.15           # net working capital as a share of revenue
  da_pct_of_ppe: 0.10                # D&A as a share of opening PP&E each year
  capex_pct_of_revenue: 0.05         # capex as a share of revenue (~= D&A so PP&E stays ~flat)
```

- [ ] **Step 2: Verify it parses**

Run: `python -c "import yaml; lbo=yaml.safe_load(open('config/config.yaml'))['lbo']; print(sorted(lbo))"`
Expected: a list including `capex_pct_of_revenue, da_pct_of_ppe, nwc_pct_of_revenue, ppe_pct_of_revenue, revenue_growth` and NOT `ebitda_growth`.

- [ ] **Step 3: Commit**

```bash
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" add config/config.yaml
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" commit -m "feat: revenue-driven operating ratios for three-statement model"
```

> Note: `run_lbo`, `app.py`, and `smoke_test.py` reference the old keys and are broken between here and their tasks. Expected.

---

## Task 2: `statements.py` — opening balance sheet

**Files:**
- Create: `src/statements.py`
- Test: `tests/test_statements.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_statements.py`:
```python
from statements import opening_balance_sheet


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_statements.py -q`
Expected: FAIL — `statements` module does not exist (ImportError).

- [ ] **Step 3: Create the module with the helper**

Create `src/statements.py`:
```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_statements.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" add src/statements.py tests/test_statements.py
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" commit -m "feat: opening balance sheet with goodwill plug"
```

---

## Task 3: `statements.py` — income statement row

**Files:**
- Modify: `src/statements.py`
- Test: `tests/test_statements.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_statements.py`:
```python
from statements import income_statement_row


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_statements.py -k income -q`
Expected: FAIL — `income_statement_row` not defined (ImportError).

- [ ] **Step 3: Add the helper**

Append to `src/statements.py`:
```python
def income_statement_row(revenue: float, margin: float, opening_ppe: float,
                         cash_interest: float, a: dict) -> dict:
    """One year of the income statement. D&A is charged on OPENING PP&E; taxes
    floor at zero in loss years (no NOL carryforward — deferred).
    """
    ebitda = revenue * margin
    da = a["da_pct_of_ppe"] * opening_ppe
    ebit = ebitda - da
    ebt = ebit - cash_interest
    taxes = a["tax_rate"] * max(0.0, ebt)
    net_income = ebt - taxes
    return {"revenue": revenue, "ebitda": ebitda, "da": da, "ebit": ebit,
            "interest": cash_interest, "ebt": ebt, "taxes": taxes,
            "net_income": net_income}
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_statements.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" add src/statements.py tests/test_statements.py
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" commit -m "feat: income statement row with D&A and tax floor"
```

---

## Task 4: Rewrite `run_lbo` as the three-statement engine

This is the core task. The headline test is "the balance sheet balances every year." It also migrates `tests/test_lbo_model.py` to the new signature/config and retires the legacy test.

**Files:**
- Modify: `src/lbo_model.py`
- Modify: `tests/test_lbo_model.py`

- [ ] **Step 1: Migrate the Phase 1 test fixtures and add the headline test**

In `tests/test_lbo_model.py`:
(a) Replace `base_assumptions()` so it returns the new config shape:
```python
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
        "nwc_pct_of_revenue": 0.15,
        "da_pct_of_ppe": 0.10,
        "capex_pct_of_revenue": 0.05,
    }
    a.update(overrides)
    return a
```
(b) DELETE the `legacy_single_tranche()` helper and the `test_single_tranche_reproduces_legacy_numbers` test entirely.
(c) Update the remaining tests to the new signature `run_lbo(entry_revenue, entry_ebitda, ...)`. Throughout the file, every `run_lbo(1000.0, a, ...)` becomes `run_lbo(5000.0, 1000.0, a, ...)` (entry revenue 5000, EBITDA 1000 → margin 0.20), and `sensitivity_grid(1000.0, a, ...)` becomes `sensitivity_grid(5000.0, 1000.0, a, ...)`. The schedule column assertions (`senior_ending`, `mezzanine_repaid`, etc.) are unchanged.
(d) Add the headline test:
```python
def test_balance_sheet_balances_every_year():
    res = run_lbo(5000.0, 1000.0, base_assumptions())
    assert res["max_balance_error"] < 1e-6
    # opening (year 0) row is present and balances too
    bs = res["balance_sheet"]
    assert (bs["year"] == 0).any()
    assert bs["balance_error"].abs().max() < 1e-6
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_lbo_model.py -q`
Expected: FAIL — current `run_lbo` has the old signature/keys; `max_balance_error` and `balance_sheet` don't exist yet.

- [ ] **Step 3: Rewrite `run_lbo`**

In `src/lbo_model.py`: keep `import pandas as pd` and `_size_tranches` unchanged. Add an import of the statement helpers near the top (after `import pandas as pd`):
```python
from statements import opening_balance_sheet, income_statement_row
```
Replace the entire `run_lbo` function with:
```python
def run_lbo(entry_revenue: float, entry_ebitda: float, assumptions: dict,
            entry_multiple: float | None = None,
            total_leverage: float | None = None) -> dict:
    """Run the paper LBO with a full three-statement build.

    Revenue drives the model; EBITDA = revenue x flat entry margin
    (entry_ebitda / entry_revenue). Each year produces an income statement, the
    debt waterfall (mandatory amort -> sweep -> revolver), a cash flow statement,
    and a balance sheet that balances. Interest accrues on opening balances, so
    the loop is a single forward pass and IRR stays closed-form.
    """
    a = assumptions
    entry_multiple = entry_multiple if entry_multiple is not None else a["entry_multiple"]
    margin = entry_ebitda / entry_revenue if entry_revenue else 0.0
    ev = entry_ebitda * entry_multiple

    sized, total_debt = _size_tranches(entry_ebitda, ev, a["tranches"], total_leverage)
    equity = ev - total_debt  # sponsor equity (entry); MOIC denominator

    balances = [t["principal"] for t in sized]
    originals = [t["principal"] for t in sized]
    rates = [t["rate"] for t in sized]
    amort_pcts = [t["mandatory_amort_pct"] for t in sized]
    names = [t["name"] for t in sized]
    revolver = 0.0

    obs = opening_balance_sheet(entry_revenue, ev, total_debt, equity, a)
    cash, nwc, ppe, goodwill = obs["cash"], obs["nwc"], obs["ppe"], obs["goodwill"]
    book_equity = equity            # accumulates retained earnings
    revenue = entry_revenue

    is_rows, cf_rows, sched_rows = [], [], []
    bs_rows = [{
        "year": 0, "cash": cash, "nwc": nwc, "ppe": ppe, "goodwill": goodwill,
        "assets": cash + nwc + ppe + goodwill, "debt": sum(balances) + revolver,
        "equity": book_equity,
        "balance_error": (cash + nwc + ppe + goodwill) - (sum(balances) + revolver + book_equity),
    }]

    for year in range(1, a["hold_years"] + 1):
        opening_ppe = ppe
        revenue = revenue * (1 + a["revenue_growth"])
        cash_interest = sum(b * r for b, r in zip(balances, rates)) + revolver * a["revolver_rate"]
        isr = income_statement_row(revenue, margin, opening_ppe, cash_interest, a)

        capex = a["capex_pct_of_revenue"] * revenue
        new_nwc = a["nwc_pct_of_revenue"] * revenue
        delta_nwc = new_nwc - nwc
        cfo = isr["net_income"] + isr["da"] - delta_nwc
        fcf_for_debt = cfo - capex

        # --- debt waterfall (same mechanism as Phase 1) ---
        mandatory = []
        for i in range(len(balances)):
            amt = min(amort_pcts[i] * originals[i], balances[i])
            balances[i] -= amt
            mandatory.append(amt)
        excess = fcf_for_debt - sum(mandatory)
        sweep = [0.0] * len(balances)
        revolver_draw = 0.0
        revolver_repaid = 0.0
        if excess > 0:
            revolver_repaid = min(revolver, excess)
            revolver -= revolver_repaid
            excess -= revolver_repaid
            for i in range(len(balances)):
                pay = min(balances[i], excess)
                balances[i] -= pay
                sweep[i] += pay
                excess -= pay
                if excess <= 1e-12:
                    break
        elif excess < 0:
            revolver_draw = -excess
            revolver += revolver_draw

        principal_repaid = sum(mandatory) + sum(sweep) + revolver_repaid
        cff = -principal_repaid + revolver_draw
        cash = cash + cfo - capex + cff

        # roll forward balances
        nwc = new_nwc
        ppe = opening_ppe + capex - isr["da"]
        book_equity = book_equity + isr["net_income"]

        ending_debt = sum(balances) + revolver
        assets = cash + nwc + ppe + goodwill

        is_rows.append({"year": year, **isr})
        cf_rows.append({
            "year": year, "net_income": isr["net_income"], "da": isr["da"],
            "delta_nwc": delta_nwc, "cfo": cfo, "capex": capex,
            "fcf_for_debt": fcf_for_debt, "principal_repaid": principal_repaid,
            "revolver_draw": revolver_draw, "cff": cff, "ending_cash": cash,
        })
        bs_rows.append({
            "year": year, "cash": cash, "nwc": nwc, "ppe": ppe,
            "goodwill": goodwill, "assets": assets, "debt": ending_debt,
            "equity": book_equity, "balance_error": assets - (ending_debt + book_equity),
        })
        srow = {"year": year, "ebitda": isr["ebitda"], "interest": cash_interest,
                "taxes": isr["taxes"], "capex": capex, "delta_nwc": delta_nwc,
                "fcf_for_debt": fcf_for_debt, "revolver": revolver, "cash": cash}
        for i, nm in enumerate(names):
            srow[f"{nm}_repaid"] = mandatory[i] + sweep[i]
            srow[f"{nm}_ending"] = balances[i]
        srow["ending_debt"] = ending_debt
        sched_rows.append(srow)

    schedule = pd.DataFrame(sched_rows)
    income_statement = pd.DataFrame(is_rows)
    cash_flow = pd.DataFrame(cf_rows)
    balance_sheet = pd.DataFrame(bs_rows)
    max_balance_error = balance_sheet["balance_error"].abs().max()

    final_ebitda = is_rows[-1]["ebitda"]
    exit_ev = final_ebitda * entry_multiple  # flat exit multiple
    ending_debt = sum(balances) + revolver
    exit_net_debt = ending_debt - cash
    exit_equity = exit_ev - exit_net_debt
    moic = exit_equity / equity if equity > 0 else float("nan")
    irr = moic ** (1 / a["hold_years"]) - 1 if moic > 0 else float("nan")

    return {
        "entry_multiple": entry_multiple,
        "margin": margin,
        "sources_uses": {
            "enterprise_value": ev,
            "debt": total_debt,
            "tranches": [{"name": t["name"], "amount": t["principal"],
                          "pct_of_ev": t["principal"] / ev} for t in sized],
            "sponsor_equity": equity,
            "debt_pct_of_ev": total_debt / ev,
        },
        "schedule": schedule,
        "income_statement": income_statement,
        "cash_flow": cash_flow,
        "balance_sheet": balance_sheet,
        "max_balance_error": max_balance_error,
        "exit_ev": exit_ev,
        "exit_net_debt": exit_net_debt,
        "exit_equity": exit_equity,
        "moic": moic,
        "irr": irr,
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_lbo_model.py -q`
Expected: PASS — the headline balance test plus the migrated waterfall/sources tests. If a waterfall test fails on a schedule column, confirm the column names (`senior_ending`, `mezzanine_repaid`, `ending_debt`) are intact.

- [ ] **Step 5: Commit**

```bash
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" add src/lbo_model.py tests/test_lbo_model.py
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" commit -m "feat: revenue-driven three-statement run_lbo"
```

---

## Task 5: Statement integrity tests

**Files:**
- Test: `tests/test_statements.py`

- [ ] **Step 1: Write the tests**

Append to `tests/test_statements.py`:
```python
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
```

- [ ] **Step 2: Run to verify it passes**

Run: `python -m pytest tests/test_statements.py -q`
Expected: PASS (all statement tests). These are properties already guaranteed by Task 4's implementation; they pin the articulation so a future change can't silently break it.

- [ ] **Step 3: Run the whole suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (test_statements + test_lbo_model).

- [ ] **Step 4: Commit**

```bash
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" add tests/test_statements.py
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" commit -m "test: three-statement integrity (cash reconciles, PP&E roll, retained earnings)"
```

---

## Task 6: `sensitivity_grid` — new signature

**Files:**
- Modify: `src/lbo_model.py` (`sensitivity_grid`)
- Test: `tests/test_lbo_model.py`

- [ ] **Step 1: Confirm the grid tests already call the new signature**

In Task 4 you updated `sensitivity_grid(...)` calls in the grid tests to `sensitivity_grid(5000.0, 1000.0, a, ...)`. Run them now to see them fail against the OLD `sensitivity_grid` signature:
Run: `python -m pytest tests/test_lbo_model.py -k grid -q`
Expected: FAIL (TypeError — old `sensitivity_grid` takes `entry_ebitda` only and calls `run_lbo` with the old signature).

- [ ] **Step 2: Update `sensitivity_grid`**

In `src/lbo_model.py`, replace `sensitivity_grid` with:
```python
def sensitivity_grid(entry_revenue: float, entry_ebitda: float, assumptions: dict,
                     entry_multiples: list[float],
                     leverage_multiples: list[float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """IRR and MOIC grids across entry multiple (rows) x total leverage (cols).

    Each column scales all tranches proportionally to the target total leverage.
    """
    irr = pd.DataFrame(index=entry_multiples, columns=leverage_multiples, dtype=float)
    moic = irr.copy()
    for em in entry_multiples:
        for lm in leverage_multiples:
            result = run_lbo(entry_revenue, entry_ebitda, assumptions,
                             entry_multiple=em, total_leverage=lm)
            irr.loc[em, lm] = result["irr"]
            moic.loc[em, lm] = result["moic"]
    irr.index.name = "entry_multiple"
    irr.columns.name = "total_leverage"
    moic.index.name = "entry_multiple"
    moic.columns.name = "total_leverage"
    return irr, moic
```

- [ ] **Step 3: Run to verify it passes**

Run: `python -m pytest tests/test_lbo_model.py -q`
Expected: PASS (all tests, including grid).

- [ ] **Step 4: Commit**

```bash
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" add src/lbo_model.py tests/test_lbo_model.py
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" commit -m "feat: sensitivity grid takes entry revenue for three-statement runs"
```

---

## Task 7: App — three-statement views + balance indicator

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Read the current tear-sheet LBO section**

Open `src/app.py`. Locate the `run_lbo(...)` call (currently passes `row["ebitda_cr"]` and `total_leverage=lev_mult`), the schedule rename block (it renames `delta_wc`/`levered_fcf` — now `delta_nwc`/`fcf_for_debt`), and the sensitivity_grid call.

- [ ] **Step 2: Update the `run_lbo` call to pass entry revenue**

Change the call to:
```python
    result = run_lbo(row["revenue_cr"], row["ebitda_cr"], assumptions,
                     entry_multiple=entry_mult, total_leverage=lev_mult)
```

- [ ] **Step 3: Add a balance-check indicator near the returns**

After the returns metrics, surface the integrity check:
```python
    if result["max_balance_error"] < 1e-6:
        st.success("Balance sheet ties ✓ (max imbalance "
                   f"₹{result['max_balance_error']:.2e} cr)")
    else:
        st.error(f"Balance sheet does NOT tie — max imbalance "
                 f"₹{result['max_balance_error']:,.2f} cr")
```

- [ ] **Step 4: Fix the schedule rename and add the three statements**

Update the schedule rename so `delta_wc`→`delta_nwc` and `levered_fcf`→`fcf_for_debt` map correctly:
```python
    base_renames = {
        "year": "Year", "ebitda": "EBITDA", "interest": "Interest",
        "taxes": "Taxes", "capex": "Capex", "delta_nwc": "ΔNWC",
        "fcf_for_debt": "FCF for debt", "revolver": "Revolver", "cash": "Cash",
        "ending_debt": "Ending debt"}
```
(keep the existing per-tranche `tranche_renames` dict-comprehension and the `line_chart` on `["Ending debt", "FCF for debt"]` — update the chart's second series name from `Levered FCF` to `FCF for debt`).

Then add IS / BS / CFS views below the schedule using tabs:
```python
    st.markdown("**Three-statement model (₹ cr)**")
    tab_is, tab_bs, tab_cf = st.tabs(["Income statement", "Balance sheet", "Cash flow"])
    with tab_is:
        st.dataframe(result["income_statement"].style.format("{:,.0f}",
                     subset=result["income_statement"].columns[1:]),
                     width="stretch", hide_index=True)
    with tab_bs:
        st.dataframe(result["balance_sheet"].style.format("{:,.0f}",
                     subset=result["balance_sheet"].columns[1:]),
                     width="stretch", hide_index=True)
    with tab_cf:
        st.dataframe(result["cash_flow"].style.format("{:,.0f}",
                     subset=result["cash_flow"].columns[1:]),
                     width="stretch", hide_index=True)
```

- [ ] **Step 5: Update the sensitivity_grid call**

```python
    irr_grid, moic_grid = sensitivity_grid(
        row["revenue_cr"], row["ebitda_cr"], assumptions,
        sens["entry_multiples"], sens["leverage_multiples"])
```

- [ ] **Step 6: Smoke-test both views render via AppTest**

Run:
```bash
python -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('src/app.py', default_timeout=90); at.run(); assert not at.exception, at.exception; at.sidebar.toggle[0].set_value(False).run(); at.sidebar.radio[0].set_value('Company tear sheet').run(); assert not at.exception, at.exception; print('app OK')"
```
Expected: prints `app OK`.

- [ ] **Step 7: Commit**

```bash
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" add src/app.py
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" commit -m "feat: three-statement tear-sheet views and balance-check indicator"
```

---

## Task 8: Update `smoke_test.py`

**Files:**
- Modify: `smoke_test.py`

- [ ] **Step 1: Update the LBO calls and assertions**

In `smoke_test.py`:
- The LBO run becomes `res = run_lbo(5000.0, 1000.0, cfg["lbo"])` (entry revenue 5000, EBITDA 1000).
- `su["debt"]`, `su["sponsor_equity"]`, `su["enterprise_value"]` checks (3000 / 5000 / 8000) and the tranche-sum check are unchanged.
- REPLACE the `res["schedule"]["ending_debt"].is_monotonic_decreasing` assertion with a net-deleveraging check (three-statement FCF may not be strictly monotonic in year 1): `assert res["schedule"]["ending_debt"].iloc[-1] < su["debt"]`.
- ADD a balance-sheet check: `assert res["max_balance_error"] < 1e-6`.
- Keep the closed-form IRR identity assertion.
- The cap check becomes `run_lbo(5000.0, 1000.0, cfg["lbo"], entry_multiple=4.0, total_leverage=3.5)`; the `0.75 * 4000` debt assertion is unchanged.
- The sensitivity call becomes `sensitivity_grid(5000.0, 1000.0, cfg["lbo"], cfg["sensitivity"]["entry_multiples"], cfg["sensitivity"]["leverage_multiples"])`; the center-cell `irr_g.loc[8.0, 3.0]` check is unchanged.
- Add a print of `res["balance_sheet"].round(0)` so the smoke run shows the statements.

- [ ] **Step 2: Run the end-to-end script**

Run: `python smoke_test.py`
Expected: prints the pipeline, the LBO line, the balance sheet, the IRR grid, and `All assertions passed.` with no traceback.

- [ ] **Step 3: Run the full pytest suite**

Run: `python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" add smoke_test.py
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" commit -m "test: end-to-end smoke test for three-statement model"
```

---

## Task 9: Update README + module docstring

**Files:**
- Modify: `README.md`
- Modify: `src/lbo_model.py` (top docstring)

- [ ] **Step 1: Update the README "Paper-LBO assumptions" section**

Describe: the model is now a **revenue-driven three-statement build** (IS/BS/CFS that tie out); revenue × flat entry margin drives EBITDA; a separate D&A schedule and PP&E roll-forward; net working capital as a % of revenue; the opening balance sheet uses a **cash-free/debt-free** convention with **goodwill as the plug** (`goodwill = EV − opening PP&E − opening NWC`). State plainly that the opening BS is **assumption-driven, not a real purchase-price allocation**. Note the **balance sheet balances every year** as the integrity check. List the new config ratios. In "Limitations", note that fees, management rollover, PIK, AR/inventory/AP days, PPA write-ups, deferred taxes, and NOLs remain out of scope.

- [ ] **Step 2: Update the `lbo_model.py` module docstring**

Replace the top docstring of `src/lbo_model.py` to describe the three-statement build (revenue driver, opening BS with goodwill plug, the yearly IS→waterfall→CFS→BS articulation, balance check, deferred items).

- [ ] **Step 3: Sanity-check**

Run: `python -m pytest tests/ -q && python smoke_test.py | tail -1`
Expected: tests pass; smoke prints `All assertions passed.`

- [ ] **Step 4: Commit**

```bash
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" add README.md src/lbo_model.py
git -c user.name="DogInfantry" -c user.email="ankleshrawat5@gmail.com" commit -m "docs: describe revenue-driven three-statement model"
```

---

## Done criteria

- `python -m pytest tests/ -q` — all tests pass (`test_statements.py` + `test_lbo_model.py`).
- `python smoke_test.py` — prints `All assertions passed.`, including `max_balance_error < 1e-6`.
- `python -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('src/app.py').run(); assert not at.exception"` — app renders with IS/BS/CFS tabs and the balance-check indicator.
- The balance sheet balances every year for the default case; returns differ from Phase 1 (real D&A in the tax line, revenue-based capex/NWC) — expected and documented.
