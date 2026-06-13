# Phase 2 Design — Three-Statement Articulation

**Date:** 2026-06-13
**Status:** Approved (design), pending implementation plan
**Scope:** Build articulating Income Statement, Balance Sheet, and Cash Flow
Statement on top of Phase 1's multi-tranche waterfall, with the balance sheet
balancing as the integrity check. Phase 2 of the model-deepening effort; builds
directly on the merged Phase 1.

## Goal & non-goals

**Goal.** Replace Phase 1's single simplified levered-FCF line with a proper
three-statement build. Each year produces an IS, a CFS, and a BS that tie out;
the cash that drives the existing debt waterfall is derived from the cash flow
statement (CFO − capex), not an EBITDA shortcut. The headline deliverable is a
balance sheet that **balances every year** (Assets = Liabilities + Equity).

**Non-goals (deferred).** Transaction & financing fees, management rollover, PIK
interest (still deferred from Phase 1), plus: working-capital split into
AR/inventory/AP via days ratios, purchase-price allocation with asset write-ups,
deferred taxes, and NOL carryforwards. Taxes floor at zero in loss years with no
carryforward.

## Fidelity: clean & articulating

Sensible simplifications, fully tied out: revenue × flat margin drives EBITDA; a
separate D&A schedule and PP&E roll-forward; a single net-working-capital line as
a % of revenue; a simplified opening balance sheet with goodwill as the balancing
plug; goodwill held flat. Opening BS inputs are **synthesized from config ratios**
— no new fundamentals-CSV columns, so data-entry burden is unchanged.

## Architecture (Approach A)

- **`src/statements.py` (new)** — pure functions: build the opening balance sheet,
  compute D&A / NWC / PP&E roll-forward, assemble the IS / BS / CFS DataFrames,
  and compute the balance check. No state, no I/O.
- **`src/lbo_model.py`** — `run_lbo` orchestrates the single yearly loop where the
  statements and the debt waterfall interlock. `_size_tranches`, the waterfall
  (mandatory amort → sweep → revolver), exit/returns, and `sensitivity_grid` are
  unchanged in mechanism. The per-year step is extracted into a helper so the
  orchestration function stays readable.

A class-based model and post-hoc statement reconstruction were both rejected
(former doesn't fit the functional codebase; latter can't keep the statements
self-consistent with the FCF that drives the sweep).

## Driver change: EBITDA-driven → revenue-driven

A balance sheet keys off operating scale, so revenue becomes the primary driver.

- **Interface change:** `run_lbo(entry_ebitda, ...)` becomes
  `run_lbo(entry_revenue, entry_ebitda, ...)` (or accepts both). Entry margin =
  `entry_ebitda / entry_revenue` is read from data and **held flat**. `app.py`
  already has `row["revenue_cr"]` and `row["ebitda_cr"]` to pass; `smoke_test.py`
  passes both.
- **New config ratios** under `lbo:` (all % of revenue unless noted), replacing
  Phase 1's `ebitda_growth` and the %-of-EBITDA operating ratios:
  - `revenue_growth` (replaces `ebitda_growth`; default 0.08 to preserve the
    prior EBITDA growth pace, since margin is flat) → EBITDA = revenue × margin.
  - `ppe_pct_of_revenue` → opening PP&E.
  - `nwc_pct_of_revenue` → net working capital each year.
  - `da_pct_of_ppe` → D&A on opening PP&E.
  - `capex_pct_of_revenue` → capex (now genuinely separate from D&A).
- **Defaults guidance:** choose `capex_pct_of_revenue` and `da_pct_of_ppe` so that
  steady-state capex ≈ D&A, keeping PP&E roughly flat over the hold (PP&E_t =
  PP&E_{t−1} + capex − D&A can otherwise drift). Document the chosen defaults.

## Opening balance sheet (cash-free, debt-free)

Day-1, post-transaction, opening cash = 0. Goodwill is the plug:

```
goodwill = EV − (opening PP&E + opening NWC)
opening PP&E = ppe_pct_of_revenue × entry_revenue
opening NWC  = nwc_pct_of_revenue × entry_revenue
```

Then opening Assets = 0 + NWC + PP&E + goodwill = EV, and opening
Liabilities + Equity = total entry debt + sponsor equity = EV. Balances by
construction. No book-equity input is needed — goodwill absorbs it. Goodwill is
held flat for the hold (no impairment). This opening BS is assumption-driven and
**not** a real purchase-price allocation; the README must say so.

## Yearly articulation

Interest accrues on **opening** balances (Phase 1 convention) so each year is a
single forward pass — no circular reference, IRR stays closed-form.

1. `revenue = prev_revenue × (1 + revenue_growth)`; `EBITDA = revenue × margin`.
2. `D&A = da_pct_of_ppe × opening_PPE`; `EBIT = EBITDA − D&A`.
3. `cash_interest = Σ(opening tranche balance × rate) + opening_revolver × revolver_rate`.
4. `EBT = EBIT − cash_interest`; `taxes = tax_rate × max(0, EBT)`;
   `net_income = EBT − taxes`.
5. `NWC_t = nwc_pct_of_revenue × revenue`; `ΔNWC = NWC_t − NWC_{t−1}`;
   `capex = capex_pct_of_revenue × revenue`.
6. `CFO = net_income + D&A − ΔNWC`; `FCF_for_debt = CFO − capex`.
7. Run the **existing waterfall** on `FCF_for_debt`: mandatory amortization first,
   then sweep excess (revolver → senior → mezz), revolver draw on a shortfall.
8. `PPE_t = PPE_{t−1} + capex − D&A`. `Cash_t` is the CFS plug:
   `Cash_t = Cash_{t−1} + CFO − capex + CFF`, where
   `CFF = −(principal repaid) + revolver draw`.
9. Build the BS and assert `|Assets − (Liabilities + Equity)| < 1e-6` (₹cr).

**Balance proof (holds by construction):** ΔAssets = ΔCash + ΔNWC + ΔPP&E =
(CFO − capex + CFF) + ΔNWC + (capex − D&A); substituting CFO = NI + D&A − ΔNWC
gives ΔAssets = NI + CFF = ΔEquity + ΔDebt = Δ(Liabilities + Equity). So the
balance check is a bug detector, not load-bearing accounting.

## Returns (unchanged shape)

- `exit_ev = entry_multiple × Year-N EBITDA` (flat exit).
- `exit_net_debt = total ending debt − ending cash`.
- `exit_equity = exit_ev − exit_net_debt`.
- `MOIC = exit_equity / sponsor_equity`; `IRR = MOIC^(1/hold) − 1` (closed form).

Returns will differ from Phase 1 because taxes now use real D&A (not the capex
proxy) and capex/NWC are revenue-based. This is an upgrade, not a regression.

## Outputs & app

- `run_lbo` return dict gains `income_statement`, `balance_sheet`, `cash_flow`
  (DataFrames) and `max_balance_error` (the largest absolute imbalance across the
  hold — should be ~0). Existing keys (`sources_uses`, `schedule`, `moic`, `irr`,
  `exit_equity`, etc.) are preserved.
- `src/app.py` tear sheet gains IS / BS / CFS views (tabs or expanders) and a
  "balance sheet ties ✓" indicator driven by `max_balance_error`.

## Testing

New `tests/test_statements.py`:

1. **Balance sheet balances every year** — `max_balance_error < 1e-6` for the
   default case (the headline integrity test).
2. **Opening BS balances** — Assets = Liabilities + Equity at Day 1.
3. **CFS cash plug reconciles** — ending cash from the CFS equals the BS cash line
   each year.
4. **IS ties** — `net_income == EBT − taxes`; `EBIT == EBITDA − D&A`.
5. **PP&E roll-forward** — `PPE_t == PPE_{t−1} + capex − D&A` each year.
6. **Retained earnings accumulate** — `equity_t == sponsor_equity + Σ net_income`.
7. **Goodwill flat** — goodwill constant across the hold.

Phase 1's waterfall *assertions* (priority invariant, mandatory amort, RBI cap)
stay valid — the waterfall mechanism is unchanged — but their shared
`base_assumptions()` fixture in `tests/test_lbo_model.py` must be updated to the
new config shape (revenue-based ratios) and their `run_lbo` calls must pass
`entry_revenue`. The `test_single_tranche_reproduces_legacy_numbers` test and the
`legacy_single_tranche()` helper are retired (Phase 2 supersedes that FCF
derivation). `smoke_test.py` is updated to pass `entry_revenue` and to
print/exercise the three statements and the balance check.

## What stays deferred

Fees, management rollover, PIK; AR/inventory/AP days-based working capital;
purchase-price write-ups; deferred taxes; NOLs.
