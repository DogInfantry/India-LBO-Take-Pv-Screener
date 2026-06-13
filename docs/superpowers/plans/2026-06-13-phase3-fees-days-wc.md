# Phase 3 Implementation Plan — Fees & Days-Based Working Capital

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add transaction fees (equity-funded, into goodwill) and financing fees (capitalized DFC asset, amortized) to Sources & Uses and the three-statement build, and replace `nwc_pct_of_revenue` with a days-based AR/Inventory/AP working-capital build.

**Architecture:** Extend the existing pure helpers in `src/statements.py` (a new `working_capital()` function; `opening_balance_sheet` and `income_statement_row` gain fee/DFC params), then wire them into the single forward pass in `src/lbo_model.py`. The balance sheet still balances by construction (the new DFC asset's roll-down cancels its CFO add-back). IRR stays closed-form. Order of operations in `run_lbo`: size tranches → RBI cap → compute both fees off post-cap `total_debt`/`ev` → equity check.

**Tech Stack:** Python, pandas, pytest, Streamlit. Tests import `src/` modules as top-level (see `tests/conftest.py`).

Spec: [docs/superpowers/specs/2026-06-13-phase3-fees-days-wc-design.md](../specs/2026-06-13-phase3-fees-days-wc-design.md)

---

### Task 1: Config & test fixture migration

**Files:**
- Modify: `config/config.yaml`
- Modify: `tests/test_lbo_model.py:4-22` (`base_assumptions`)
- Modify: `tests/test_statements.py:4-7` (`ratios`)

- [ ] **Step 1: Update `config/config.yaml`** — under `lbo:`, remove `nwc_pct_of_revenue`; add the new keys. Replace the WC line with:

```yaml
  txn_fee_pct_of_ev: 0.020        # M&A/legal/diligence fees, % of EV (equity-funded, into goodwill)
  financing_fee_pct_of_debt: 0.025 # arrangement/OID fees, % of debt (capitalized, amortized over hold)
  cogs_pct_of_revenue: 0.65        # COGS base for inventory & payables days
  working_capital:
    dso_days: 45                   # receivables days, against revenue
    dio_days: 60                   # inventory days, against COGS
    dpo_days: 40                   # payables days, against COGS
```

(Leave `ppe_pct_of_revenue`, `da_pct_of_ppe`, `capex_pct_of_revenue`, `revenue_growth` as-is.)

- [ ] **Step 2: Update `base_assumptions()` in `tests/test_lbo_model.py`** — drop `"nwc_pct_of_revenue": 0.15`; add:

```python
        "txn_fee_pct_of_ev": 0.020,
        "financing_fee_pct_of_debt": 0.025,
        "cogs_pct_of_revenue": 0.65,
        "working_capital": {"dso_days": 45, "dio_days": 60, "dpo_days": 40},
```

- [ ] **Step 3: Update `ratios()` in `tests/test_statements.py`** — drop `nwc_pct_of_revenue`; add the same four keys (`txn_fee_pct_of_ev`, `financing_fee_pct_of_debt`, `cogs_pct_of_revenue`, `working_capital`). This helper is used directly by the opening-BS unit test, so it must carry the new shape.

- [ ] **Step 4: Run the suite to see the expected breakage**

Run: `python -m pytest -q`
Expected: failures referencing `nwc_pct_of_revenue` KeyError (the code still reads it). This confirms the fixture migration is the next dependency. Proceed to Task 2.

- [ ] **Step 5: Commit**

```bash
git add config/config.yaml tests/test_lbo_model.py tests/test_statements.py
git commit -m "config: add fee + days-WC assumptions, drop nwc_pct_of_revenue"
```

---

### Task 2: `working_capital()` helper (days-based)

**Files:**
- Modify: `src/statements.py`
- Test: `tests/test_statements.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_statements.py`):

```python
from statements import working_capital


def test_working_capital_days_based():
    a = ratios()  # dso 45, dio 60, dpo 40, cogs 0.65
    wc = working_capital(10000.0, a)
    assert abs(wc["ar"] - 45 / 365 * 10000.0) < 1e-9
    assert abs(wc["inventory"] - 60 / 365 * 0.65 * 10000.0) < 1e-9
    assert abs(wc["ap"] - 40 / 365 * 0.65 * 10000.0) < 1e-9
    assert abs(wc["nwc"] - (wc["ar"] + wc["inventory"] - wc["ap"])) < 1e-12
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_statements.py::test_working_capital_days_based -v`
Expected: FAIL — `ImportError: cannot import name 'working_capital'`.

- [ ] **Step 3: Implement `working_capital()` in `src/statements.py`** (add above `opening_balance_sheet`):

```python
def working_capital(revenue: float, a: dict) -> dict:
    """Days-based net working capital. AR keys off revenue; inventory and AP
    key off COGS (cogs_pct_of_revenue x revenue). NWC = AR + Inventory - AP.
    """
    wc = a["working_capital"]
    cogs = a["cogs_pct_of_revenue"] * revenue
    ar = wc["dso_days"] / 365 * revenue
    inventory = wc["dio_days"] / 365 * cogs
    ap = wc["dpo_days"] / 365 * cogs
    return {"ar": ar, "inventory": inventory, "ap": ap,
            "nwc": ar + inventory - ap}
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_statements.py::test_working_capital_days_based -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/statements.py tests/test_statements.py
git commit -m "feat: days-based working-capital helper (DSO/DIO/DPO)"
```

---

### Task 3: `opening_balance_sheet` — fees + days WC

**Files:**
- Modify: `src/statements.py` (`opening_balance_sheet`)
- Test: `tests/test_statements.py` (replace `test_opening_balance_sheet_balances`)

**Interface change:** `opening_balance_sheet(entry_revenue, ev, total_debt, sponsor_equity, a, txn_fees=0.0, financing_fees=0.0)`. NWC comes from `working_capital`; goodwill includes `txn_fees`; returned dict gains `dfc` (= `financing_fees`). New-keyword defaults of 0.0 keep it safe, but `run_lbo` always passes them.

- [ ] **Step 1: Rewrite the failing test** — replace `test_opening_balance_sheet_balances` in `tests/test_statements.py` with:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_statements.py::test_opening_balance_sheet_balances_with_fees -v`
Expected: FAIL — `TypeError` (unexpected kwarg) or missing `dfc` key.

- [ ] **Step 3: Rewrite `opening_balance_sheet`** in `src/statements.py`:

```python
def opening_balance_sheet(entry_revenue: float, ev: float, total_debt: float,
                          sponsor_equity: float, a: dict,
                          txn_fees: float = 0.0, financing_fees: float = 0.0) -> dict:
    """Day-1 post-deal balance sheet. Cash-free/debt-free: opening cash is zero.
    Transaction fees roll into goodwill (equity-funded); financing fees are a
    capitalized deferred-financing-cost (DFC) asset. Goodwill is the plug that
    makes Assets = Liabilities + Equity.
    """
    ppe = a["ppe_pct_of_revenue"] * entry_revenue
    nwc = working_capital(entry_revenue, a)["nwc"]
    goodwill = ev + txn_fees - (ppe + nwc)
    return {"cash": 0.0, "nwc": nwc, "ppe": ppe, "goodwill": goodwill,
            "dfc": financing_fees, "debt": total_debt, "equity": sponsor_equity}
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_statements.py::test_opening_balance_sheet_balances_with_fees -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/statements.py tests/test_statements.py
git commit -m "feat: opening balance sheet folds in fees + days-based NWC"
```

---

### Task 4: `income_statement_row` — DFC amortization

**Files:**
- Modify: `src/statements.py` (`income_statement_row`)
- Test: `tests/test_statements.py` (extend `test_income_statement_ties`)

**Interface change:** `income_statement_row(revenue, margin, opening_ppe, cash_interest, a, dfc_amort=0.0)`. `dfc_amort` is a non-cash expense subtracted after D&A and before interest; row gains `dfc_amort`. EBT = EBITDA − D&A − dfc_amort − interest.

- [ ] **Step 1: Write the failing test** (append to `tests/test_statements.py`):

```python
def test_income_statement_includes_dfc_amortization():
    a = ratios()
    # revenue 5400, margin 0.20, opening PP&E 2000, interest 300, dfc_amort 15.
    isr = income_statement_row(5400.0, 0.20, 2000.0, 300.0, a, dfc_amort=15.0)
    assert abs(isr["dfc_amort"] - 15.0) < 1e-9
    # EBITDA 1080, D&A 200, dfc 15, interest 300 -> EBT = 1080-200-15-300 = 565
    assert abs(isr["ebt"] - 565.0) < 1e-9
    assert abs(isr["taxes"] - 0.25 * 565.0) < 1e-9
    assert abs(isr["net_income"] - (565.0 - 0.25 * 565.0)) < 1e-9
```

Also update the existing `test_income_statement_ties` to pass `a` (it currently passes `ratios()` positionally as the 5th arg — still correct) and to expect `isr["dfc_amort"] == 0.0` by default.

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_statements.py::test_income_statement_includes_dfc_amortization -v`
Expected: FAIL — missing `dfc_amort` key / kwarg.

- [ ] **Step 3: Rewrite `income_statement_row`** in `src/statements.py`:

```python
def income_statement_row(revenue: float, margin: float, opening_ppe: float,
                         cash_interest: float, a: dict,
                         dfc_amort: float = 0.0) -> dict:
    """One year of the income statement. D&A on OPENING PP&E; DFC amortization is
    a non-cash expense after D&A; taxes floor at zero in loss years (no NOL).
    """
    ebitda = revenue * margin
    da = a["da_pct_of_ppe"] * opening_ppe
    ebit = ebitda - da - dfc_amort
    ebt = ebit - cash_interest
    taxes = a["tax_rate"] * max(0.0, ebt)
    net_income = ebt - taxes
    return {"revenue": revenue, "ebitda": ebitda, "da": da, "dfc_amort": dfc_amort,
            "ebit": ebit, "interest": cash_interest, "ebt": ebt, "taxes": taxes,
            "net_income": net_income}
```

Note: `dfc_amort` is folded into EBIT here for a single clean subtraction chain. The README/docstring should note EBIT is reported net of DFC amortization.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_statements.py -k income_statement -v`
Expected: PASS (both the new test and the updated ties test).

- [ ] **Step 5: Commit**

```bash
git add src/statements.py tests/test_statements.py
git commit -m "feat: income statement charges DFC amortization"
```

---

### Task 5: Wire fees + days WC into `run_lbo`

**Files:**
- Modify: `src/lbo_model.py` (`run_lbo`, docstring lines ~1-22)
- Test: `tests/test_statements.py` (new integrity tests), `tests/test_lbo_model.py` (`test_sources_equal_uses`)

This is the core wiring. Do it in one implementation pass guarded by the tests below.

- [ ] **Step 1: Write the failing integrity tests** (append to `tests/test_statements.py`; `model()` already runs the default case):

```python
def test_sources_uses_ties_with_fees():
    res = model()
    su = res["sources_uses"]
    assert abs(su["enterprise_value"] + su["txn_fees"] + su["financing_fees"]
               - (su["debt"] + su["sponsor_equity"])) < 1e-6


def test_fees_raise_equity_check():
    from test_lbo_model import base_assumptions
    with_fees = run_lbo(5000.0, 1000.0, base_assumptions())
    no_fees = run_lbo(5000.0, 1000.0,
                      base_assumptions(txn_fee_pct_of_ev=0.0,
                                       financing_fee_pct_of_debt=0.0))
    delta = (with_fees["sources_uses"]["txn_fees"]
             + with_fees["sources_uses"]["financing_fees"])
    assert delta > 0
    assert abs((with_fees["sources_uses"]["sponsor_equity"]
                - no_fees["sources_uses"]["sponsor_equity"]) - delta) < 1e-6


def test_dfc_rolls_down_to_zero():
    res = model()
    bs = res["balance_sheet"].set_index("year")
    hold = bs.index.max()
    assert abs(bs.loc[hold, "dfc"]) < 1e-6
    # strictly declining each year by a constant amount
    diffs = bs["dfc"].diff().dropna()
    assert (diffs < 0).all()
    assert diffs.nunique() == 1  # straight-line, constant step


def test_balance_sheet_still_balances_with_fees_and_days_wc():
    res = model()
    assert res["max_balance_error"] < 1e-6


def test_balance_sheet_nwc_is_days_based():
    res = model()
    bs = res["balance_sheet"].set_index("year")
    for year in bs.index:
        if year == 0:
            continue
        assert abs(bs.loc[year, "nwc"]
                   - (bs.loc[year, "ar"] + bs.loc[year, "inventory"]
                      - bs.loc[year, "ap"])) < 1e-6
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_statements.py -k "fees or dfc or days_wc or balances_with" -v`
Expected: FAIL — `KeyError: 'txn_fees'` / missing `ar`/`dfc` BS columns.

- [ ] **Step 3: Edit `run_lbo` in `src/lbo_model.py`.** Apply these changes:

  **(a) After `_size_tranches` (line ~72), compute fees and equity off post-cap debt:**
```python
    sized, total_debt = _size_tranches(entry_ebitda, ev, a["tranches"], total_leverage)
    txn_fees = a["txn_fee_pct_of_ev"] * ev
    financing_fees = a["financing_fee_pct_of_debt"] * total_debt
    dfc_amort = financing_fees / a["hold_years"] if a["hold_years"] else 0.0
    equity = ev + txn_fees + financing_fees - total_debt  # sponsor equity (entry); MOIC denominator
```

  **(b) Opening BS call — pass fees; capture `dfc`:**
```python
    obs = opening_balance_sheet(entry_revenue, ev, total_debt, equity, a,
                                txn_fees=txn_fees, financing_fees=financing_fees)
    cash, nwc, ppe, goodwill = obs["cash"], obs["nwc"], obs["ppe"], obs["goodwill"]
    dfc = obs["dfc"]
```

  **(c) Year-0 BS row — add `ar`/`inventory`/`ap`/`dfc`; include `dfc` in assets and balance_error.** Compute opening WC components once:
```python
    from statements import working_capital  # already importable; or add to top import
    wc0 = working_capital(entry_revenue, a)
    bs_rows = [{
        "year": 0, "cash": cash, "ar": wc0["ar"], "inventory": wc0["inventory"],
        "ap": wc0["ap"], "nwc": nwc, "ppe": ppe, "goodwill": goodwill, "dfc": dfc,
        "assets": cash + nwc + ppe + goodwill + dfc,
        "debt": sum(balances) + revolver, "equity": book_equity,
        "balance_error": (cash + nwc + ppe + goodwill + dfc)
                         - (sum(balances) + revolver + book_equity),
    }]
```
  (Prefer adding `working_capital` to the existing top-of-file import:
  `from statements import opening_balance_sheet, income_statement_row, working_capital`.)

  **(d) Inside the yearly loop — days-based WC, DFC amort into IS, DFC add-back in CFO, roll DFC down:**
```python
        revenue = revenue * (1 + a["revenue_growth"])
        wc = working_capital(revenue, a)
        cash_interest = sum(b * r for b, r in zip(balances, rates)) + revolver * a["revolver_rate"]
        isr = income_statement_row(revenue, margin, opening_ppe, cash_interest, a,
                                   dfc_amort=dfc_amort)

        capex = a["capex_pct_of_revenue"] * revenue
        delta_nwc = wc["nwc"] - nwc
        cfo = isr["net_income"] + isr["da"] + isr["dfc_amort"] - delta_nwc
        fcf_for_debt = cfo - capex
```
  (Waterfall block unchanged.)

  **(e) Roll-forwards after the waterfall:**
```python
        nwc = wc["nwc"]
        ppe = opening_ppe + capex - isr["da"]
        dfc = max(0.0, dfc - dfc_amort)
        book_equity = book_equity + isr["net_income"]
```

  **(f) Ending BS — add components + dfc to assets and balance_error:**
```python
        assets = cash + nwc + ppe + goodwill + dfc
        ...
        bs_rows.append({
            "year": year, "cash": cash, "ar": wc["ar"], "inventory": wc["inventory"],
            "ap": wc["ap"], "nwc": nwc, "ppe": ppe, "goodwill": goodwill, "dfc": dfc,
            "assets": assets, "debt": ending_debt, "equity": book_equity,
            "balance_error": assets - (ending_debt + book_equity),
        })
```

  **(g) `sources_uses` return — add fee lines:**
```python
        "sources_uses": {
            "enterprise_value": ev,
            "debt": total_debt,
            "tranches": [{"name": t["name"], "amount": t["principal"],
                          "pct_of_ev": t["principal"] / ev} for t in sized],
            "txn_fees": txn_fees,
            "financing_fees": financing_fees,
            "sponsor_equity": equity,
            "debt_pct_of_ev": total_debt / ev,
        },
```

  **(h) Update the module docstring (lines ~1-22):** note fees in S&U, DFC capitalization/amortization, and that working capital is now days-based (DSO/DIO/DPO). Remove "transaction fees", "financing fees", and "days-based working capital" from the *Deferred* list; keep management rollover, PIK, write-ups, deferred taxes, NOLs.

- [ ] **Step 4: Run the new integrity tests, then the full suite**

Run: `python -m pytest tests/test_statements.py -k "fees or dfc or days_wc or balances_with" -v`
Expected: PASS.
Run: `python -m pytest -q`
Expected: ALL green. `test_sources_equal_uses` in `tests/test_lbo_model.py` will now FAIL (it asserts `debt + equity == EV` with no fees) — update it to `assert abs(su["debt"] + su["sponsor_equity"] - (su["enterprise_value"] + su["txn_fees"] + su["financing_fees"])) < 1e-9` in the same step, then re-run until green.

- [ ] **Step 5: Commit**

```bash
git add src/lbo_model.py tests/test_statements.py tests/test_lbo_model.py
git commit -m "feat: fees + days-based WC threaded through run_lbo three-statement build"
```

---

### Task 6: App tear sheet — fee lines, DFC, AR/Inv/AP

**Files:**
- Modify: `src/app.py` (Sources & Uses block ~144-156; schedule renames ~175-179; BS/IS tabs ~189-199)

- [ ] **Step 1: Add fee rows to Sources & Uses** — in the `su_rows` build (~148-152), insert the fee lines before Sponsor equity:

```python
        su_rows += [("Total debt", su["debt"]),
                    ("Transaction fees", su["txn_fees"]),
                    ("Financing fees (capitalized)", su["financing_fees"]),
                    ("Sponsor equity", su["sponsor_equity"]),
                    ("Enterprise value", su["enterprise_value"])]
```

- [ ] **Step 2: Caption note** — after the existing RBI caption (~155-156), add:

```python
        st.caption(f"Equity check includes ₹{su['txn_fees'] + su['financing_fees']:,.0f} cr "
                   "of fees (transaction expensed into goodwill; financing capitalized & amortized).")
```

- [ ] **Step 3: BS/IS columns render automatically** — the IS tab now shows a `dfc_amort` column and the BS tab shows `ar`/`inventory`/`ap`/`dfc` because they format `columns[1:]` generically (no per-column list to edit). Confirm by reading the tab blocks (~189-199); no code change expected. If column headers look raw (e.g. `dfc_amort`), optionally add friendly renames mirroring the `base_renames` pattern — keep it minimal.

- [ ] **Step 4: Smoke-run the app non-interactively** to catch import/key errors:

Run: `python -c "import sys; sys.path.insert(0, 'src'); import app"`
Expected: no exception (module imports; Streamlit script body guarded by `__main__`/`st` calls — if it executes st calls on import, instead run a Streamlit AppTest if one exists, or `python -m streamlit run src/app.py` briefly and Ctrl-C). Prefer: `python -m py_compile src/app.py` for a guaranteed syntax/import-free check.

- [ ] **Step 5: Commit**

```bash
git add src/app.py
git commit -m "feat: tear sheet shows fees, DFC, and AR/Inventory/AP breakout"
```

---

### Task 7: Smoke test, README, config comments

**Files:**
- Modify: `smoke_test.py`
- Modify: `README.md`

- [ ] **Step 1: Update `smoke_test.py`** — add assertions: Sources & Uses ties with fees (`EV + txn + fin == debt + equity`), `txn_fees > 0` and `financing_fees > 0`, DFC at final year ≈ 0, and keep the existing balance-error and net-deleverage checks. Print the fee lines and a sample BS row showing `ar`/`inventory`/`ap`/`dfc`.

- [ ] **Step 2: Run the smoke test**

Run: `python smoke_test.py`
Expected: all assertions pass; printed S&U shows the two fee lines; balance error < 1e-6.

- [ ] **Step 3: Update `README.md`** — in the model-description section: document the two fee types (expensed-into-goodwill vs capitalized-DFC-amortized), the days-based WC build (DSO/DIO/DPO, inventory/AP on COGS), note default returns drop vs Phase 2 (entry fee drag, partially offset by the DFC tax shield), and the simplification that transaction fees go into goodwill (no Year-0 IS). Move fees + days-WC out of any "deferred/future" list.

- [ ] **Step 4: Grep for stragglers**

Run: `git grep -n "nwc_pct_of_revenue"`
Expected: no matches outside the spec/plan docs. If `src/screener.py` or any code references it, fix or remove.

- [ ] **Step 5: Commit**

```bash
git add smoke_test.py README.md
git commit -m "test+docs: smoke test asserts fee mechanics; README documents Phase 3"
```

---

### Task 8: Final verification

- [ ] **Step 1: Full suite**

Run: `python -m pytest -q`
Expected: all tests green (Phase 1/2 waterfall + three-statement tests, plus new Phase 3 tests).

- [ ] **Step 2: Smoke test**

Run: `python smoke_test.py`
Expected: all assertions pass.

- [ ] **Step 3: Confirm returns moved the right direction** — eyeball the smoke-test MOIC/IRR printout: should be *below* Phase 2's ~2.18x / ~16.9% (bigger equity check from fees). Note the new figures in the commit message / project memory.

- [ ] **Step 4: Merge prep** — this branch (`feat/phase3-fees-days-wc`) is ready for the finishing-a-development-branch flow (merge to main, push). Do not merge until the user confirms.

---

## Notes for the implementer

- **Order of operations is load-bearing:** size tranches → RBI cap → fees off post-cap `total_debt`/`ev` → equity. Computing financing fees before the cap would overstate them.
- **The balance check is the safety net.** If `max_balance_error` is non-trivial after Task 5, the most likely culprit is forgetting `dfc` in either `assets` or the CFO add-back — they must both move by `dfc_amort` each year so they cancel.
- **DFC straight-line over the full hold** means `dfc_amort` is constant and DFC hits exactly 0 at `hold_years`; the `max(0, ...)` floor never actually clamps.
