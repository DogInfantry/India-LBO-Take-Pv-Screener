# Phase 3 Design — Transaction/Financing Fees & Days-Based Working Capital

**Date:** 2026-06-13
**Status:** Approved (design), pending implementation plan
**Scope:** Add (A) transaction and financing fees to Sources & Uses and the
three-statement build, and (B) a days-based working-capital build (DSO/DIO/DPO)
that replaces the blunt `nwc_pct_of_revenue` line. Phase 3 of the model-deepening
effort; builds directly on the merged Phase 2 three-statement model.

## Goal & non-goals

**Goal.** Make the entry economics and the working-capital build defensible in a
PE/IB interview — the two questions most often asked of a paper LBO ("walk me
through Sources & Uses" and "how did you model working capital"). Fees enlarge
the sponsor's equity check (the realistic return drag) and introduce the
expensed-vs-capitalized distinction; days-based WC replaces a single % with the
textbook AR + Inventory − AP build keyed off revenue and COGS.

**Non-goals (still deferred).** Management rollover, PIK interest, purchase-price
allocation with asset write-ups, deferred taxes, and NOL carryforwards. Exit
stays at a flat multiple. IRR stays closed-form; the model stays a single forward
pass with the balance sheet balancing by construction.

## Part A — Fees

Two distinct fee types, because real LBOs carry both and they flow differently.

### A1. Transaction fees (expensed / equity-funded)

M&A advisory, legal, diligence. New config `txn_fee_pct_of_ev` (default 0.02).

- `txn_fees = txn_fee_pct_of_ev × EV`.
- **Sources & Uses:** they are a *use* funded by sponsor equity. The equity check
  becomes `equity = EV + txn_fees + financing_fees − total_debt`. Debt sizing is
  unchanged (turns × EBITDA, capped at 75% of EV — fees do **not** enlarge the
  debt the RBI cap applies to).
- **Day-1 balance sheet:** they roll into **goodwill**, so the BS still balances
  with no Year-0 income-statement event:
  `goodwill = EV + txn_fees − (opening PP&E + opening NWC)`.
- *Effect:* larger equity denominator → lower MOIC/IRR. They do not touch exit
  (exit equity is EV-driven), so their entire impact is the entry drag.

> **Why fold transaction fees into goodwill rather than expense them in a Year-0
> IS?** Strict Ind-AS expenses acquisition-related costs, but a paper LBO has no
> Year-0 income statement; adding one breaks the clean single forward pass.
> Folding them into goodwill (equity-funded, parked on the BS, irrelevant at an
> EV-based exit) is the standard paper-LBO shortcut. Documented as a known
> simplification in the README and the model docstring.

### A2. Financing fees / OID (capitalized / amortized)

Arrangement and underwriting fees on the debt raised. New config
`financing_fee_pct_of_debt` (default 0.025).

- `financing_fees = financing_fee_pct_of_debt × total_debt` (computed on the
  RBI-capped, post-scaling `total_debt`, so the grid scales it automatically).
- Capitalized as a **deferred financing cost (DFC) asset** on the opening BS,
  amortized **straight-line over `hold_years`**:
  `dfc_amort = financing_fees / hold_years` each year.
- DFC amortization is a **non-cash expense on the IS** (reduces EBT → small tax
  shield) and is **added back in CFO** like D&A. The DFC asset rolls down
  `DFC_t = DFC_{t−1} − dfc_amort`, reaching ~0 at exit.
- *Effect:* both a return drag (bigger equity check) and a modest tax shield —
  demonstrates the expensed-vs-capitalized distinction.

### Day-1 balance with both fees (balances by construction)

```
total_uses    = EV + txn_fees + financing_fees
equity        = total_uses − total_debt
opening PP&E  = ppe_pct_of_revenue × entry_revenue
opening NWC   = (days-based, see Part B)
DFC asset     = financing_fees
goodwill      = EV + txn_fees − (opening PP&E + opening NWC)
```

Proof: `Assets = 0 + NWC + PP&E + goodwill + DFC`
`= NWC + PP&E + (EV + txn_fees − PP&E − NWC) + financing_fees`
`= EV + txn_fees + financing_fees = total_uses = total_debt + equity`. ✓

## Part B — Days-based working capital

Replace `nwc_pct_of_revenue × revenue` with the textbook build. Inventory and AP
key off COGS, so the model now tracks COGS via a new ratio.

New config (a `working_capital:` block replaces `nwc_pct_of_revenue`):

```yaml
working_capital:
  dso_days: 45     # accounts receivable, against revenue
  dio_days: 60     # inventory, against COGS
  dpo_days: 40     # accounts payable, against COGS
cogs_pct_of_revenue: 0.65   # COGS base for inventory & AP
```

Each year (and at the opening BS, using entry revenue):

```
COGS      = cogs_pct_of_revenue × revenue
AR        = (dso_days / 365) × revenue
Inventory = (dio_days / 365) × COGS
AP        = (dpo_days / 365) × COGS
NWC       = AR + Inventory − AP
```

`ΔNWC = NWC_t − NWC_{t−1}` flows into CFO exactly as today. NWC now grows with
revenue/COGS organically. The balance sheet gains `ar`, `inventory`, `ap` line
items for presentation; the **net `nwc`** is what drives ΔNWC and the cash plug,
so the balance check is untouched. Default days are chosen so opening NWC stays
close to the old 15%-of-revenue level (keeps default returns comparable; the
delta comes from fees, not a WC discontinuity) — the implementation plan
verifies and documents the resulting opening NWC.

## Architecture (follows the Phase 2 shape)

- **`src/statements.py`** — extend the pure helpers:
  - `working_capital(revenue, a) -> dict` returns `{ar, inventory, ap, nwc}` from
    the days ratios (used by both the opening BS and the yearly loop).
  - `opening_balance_sheet(...)` gains `txn_fees` and `financing_fees` params:
    goodwill includes `txn_fees`, the returned dict gains `dfc`, and NWC comes
    from `working_capital`.
  - `income_statement_row(...)` gains a `dfc_amort` param: it is subtracted after
    D&A and before interest (a non-cash operating-ish expense), so EBT and the tax
    shield reflect it. Returned row gains `dfc_amort`.
- **`src/lbo_model.py`** — `run_lbo` computes `txn_fees`/`financing_fees` after
  sizing tranches, threads them into the opening BS and the equity check, carries
  `dfc` as a rolled-down asset in the BS (and in the balance-error term), and adds
  `dfc_amort` back in CFO. `sources_uses` gains `txn_fees`, `financing_fees`, and
  the larger `sponsor_equity`. The waterfall, `_size_tranches`, exit/returns, and
  `sensitivity_grid` mechanisms are unchanged.
- **`config/config.yaml`** — add `txn_fee_pct_of_ev`, `financing_fee_pct_of_debt`,
  a `working_capital:` block, and `cogs_pct_of_revenue`; remove
  `nwc_pct_of_revenue`.
- **`src/screener.py`** — no change expected (it reads tranche turns, not WC/fees);
  verify the `nwc_pct_of_revenue` key is not referenced anywhere before removing it.

## Yearly articulation (deltas from Phase 2)

Insert into the existing forward pass:

1. After computing `revenue`: `wc = working_capital(revenue, a)`;
   `ΔNWC = wc["nwc"] − prev_nwc`.
2. `cash_interest` unchanged (opening balances).
3. IS: `income_statement_row(revenue, margin, opening_ppe, cash_interest,
   dfc_amort, a)` — `dfc_amort = financing_fees / hold_years` (constant, zeroed
   once the DFC asset is exhausted; with straight-line over the full hold it is
   simply constant).
4. `CFO = net_income + D&A + dfc_amort − ΔNWC`; `FCF_for_debt = CFO − capex`.
5. Waterfall unchanged.
6. Roll forward: `nwc = wc["nwc"]`; `ppe = opening_ppe + capex − D&A`;
   `dfc = dfc − dfc_amort`; `book_equity += net_income`.
7. BS: assets `= cash + nwc + ppe + goodwill + dfc`; `balance_error = assets −
   (ending_debt + book_equity)`; assert `< 1e-6` (₹cr).

**Balance proof (extended):** ΔAssets now includes `ΔDFC = −dfc_amort`, and CFO
now includes `+dfc_amort`. ΔCash picks up the same `+dfc_amort` (via CFO), so the
two cancel: ΔAssets = NI + CFF = ΔEquity + ΔDebt, exactly as Phase 2. The balance
check remains a bug detector.

## Returns

Default MOIC/IRR drop versus Phase 2 because the equity check grows by
`txn_fees + financing_fees` (~2% of EV + ~2.5% of debt). The DFC tax shield claws
back a small amount. Net direction is lower and more realistic — an upgrade, to be
documented alongside the Phase 1→2 progression.

## Outputs & app

- `run_lbo` return: `sources_uses` gains `txn_fees`, `financing_fees`;
  `income_statement` gains a `dfc_amort` column; `balance_sheet` gains `ar`,
  `inventory`, `ap`, `dfc` columns. Existing keys preserved.
- `src/app.py` tear sheet: Sources & Uses itemizes the two fee lines and the
  enlarged equity check; the IS view shows DFC amortization; the BS view breaks
  out AR / Inventory / AP and shows the DFC asset rolling down. The "balance
  sheet ties ✓" indicator is unchanged.

## Testing

Extend `tests/test_statements.py` (or a new `tests/test_fees_wc.py`):

1. **Sources & Uses ties** — `EV + txn_fees + financing_fees == total_debt +
   sponsor_equity`.
2. **Fees raise the equity check** — equity with fees > equity with fees zeroed,
   by exactly `txn_fees + financing_fees`.
3. **Opening BS balances with fees** — Assets (incl. DFC) = Liabilities + Equity.
4. **DFC rolls to ~0** — `DFC` at year `hold_years` ≈ 0; declines by `dfc_amort`
   each year.
5. **DFC amortization hits the IS** — EBT is lower by `dfc_amort` vs a no-DFC run;
   it is added back in CFO (CFO unchanged by DFC at the cash level).
6. **Days-based WC ties** — `nwc == AR + Inventory − AP` each year; AR/Inv/AP
   match the days formulas against revenue/COGS.
7. **Balance sheet still balances** — `max_balance_error < 1e-6` (the headline
   integrity test, now with fees + days-based WC).

The Phase 2 waterfall and three-statement assertions stay valid (mechanisms
unchanged); the shared `base_assumptions()` fixture is updated to the new config
shape (fee keys, `working_capital` block, `cogs_pct_of_revenue`; drop
`nwc_pct_of_revenue`). `smoke_test.py` is updated to assert Sources & Uses ties
with fees, the DFC roll-down, and the balance check, and to print the fee lines.

## What stays deferred

Management rollover, PIK; purchase-price write-ups; deferred taxes; NOLs. Flat
exit multiple.
