# Phase 1 Design — Multi-Tranche Debt & Cash-Sweep Waterfall

**Date:** 2026-06-13
**Status:** Approved (design), pending implementation plan
**Scope:** Deepen the paper LBO with realistic debt structure. Phase 1 of a two-phase
effort; Phase 2 (three-statement articulation) is a separate, later spec.

## Goal & non-goals

**Goal.** Replace the single-debt LBO engine with a multi-tranche structure and a real
cash-sweep waterfall, so the model demonstrates how senior/mezzanine debt is serviced and
repaid in priority order — the core mechanic of a real underwriting model.

**Non-goals (deferred).** Transaction & financing fees, management rollover, PIK interest,
and the full three-statement (IS/BS/CFS) articulation are explicitly out of Phase 1. They
are noted only where they affect a seam that Phase 1 should leave clean.

## Design principle: default-equivalence

The default config sums to 3.0x total leverage — identical to today's single 3.0x debt
default. With one senior tranche at 3.0x and no mezz, the new engine must reproduce the
current model's numbers. This keeps the existing smoke-test expectations valid and isolates
the new behaviour to multi-tranche configs.

## Config shape

`config/config.yaml` — the scalar `leverage_multiple` and `interest_rate` become an ordered
`tranches` list plus a revolver rate. List order encodes sweep priority (index 0 = most
senior).

```yaml
lbo:
  entry_multiple: 8.0
  tranches:
    - {name: senior,    turns: 2.0, rate: 0.090, mandatory_amort_pct: 0.10}
    - {name: mezzanine, turns: 1.0, rate: 0.130, mandatory_amort_pct: 0.0}
  revolver_rate: 0.085
  ebitda_growth: 0.08
  hold_years: 5
  tax_rate: 0.25
  capex_pct_of_ebitda: 0.25
  wc_pct_of_incremental_ebitda: 0.20
```

- `turns` — tranche size as a multiple of LTM EBITDA.
- `rate` — cash interest rate on the tranche.
- `mandatory_amort_pct` — fraction of *original* principal repaid contractually each year
  (0.0 = bullet).
- `revolver_rate` — interest on drawn revolver balance.

## Sources & uses

- `EV = entry_multiple × LTM EBITDA`.
- `total_entry_debt = Σ(tranche turns) × EBITDA`, **capped at 0.75 × EV** (RBI
  acquisition-finance ceiling). If the cap binds, every tranche scales down by the same
  factor `0.75 × EV / total_entry_debt`.
- `sponsor_equity = EV − total_entry_debt` (no fees in Phase 1).
- Output itemizes each tranche's entry quantum and its % of EV, plus the total.

## Yearly waterfall

For each year 1..hold_years:

1. `EBITDA = prev_EBITDA × (1 + ebitda_growth)`.
2. `cash_interest = Σ(opening_balanceᵢ × rateᵢ)` over all tranches + revolver on its opening
   balance.
3. `taxes = tax_rate × max(0, EBITDA − capex − cash_interest)` — capex doubles as the D&A
   proxy (unchanged convention); tax shield uses *total* cash interest.
4. `capex = capex_pct_of_ebitda × EBITDA`; `ΔWC = wc_pct_of_incremental_ebitda × (EBITDA −
   prev_EBITDA)`.
5. `levered_fcf = EBITDA − cash_interest − taxes − capex − ΔWC`.
6. **Mandatory amortization** (contractual, paid first): each tranche pays
   `min(mandatory_amort_pct × original_principal, current_balance)`.
7. `excess = levered_fcf − total_mandatory_amort`.
   - `excess > 0` → **cash sweep** down the priority stack: revolver first, then tranches in
     list order, each paying `min(excess_remaining, balance)`.
   - `excess < 0` → revolver draw funds the shortfall (`revolver += −excess`).
8. Any cash remaining after *all* debt is fully repaid accumulates as cash, returned at exit.

**Core invariant (becomes a test):** a junior tranche's principal cannot be reduced by the
sweep while any more-senior tranche has a positive balance. Mandatory amort is the only way
a junior balance moves before senior is retired.

## Exit & returns (math unchanged)

- `exit_ev = entry_multiple × Year-N EBITDA` (flat exit multiple).
- `exit_net_debt = Σ(ending tranche balances) + ending_revolver − ending_cash`.
- `exit_equity = exit_ev − exit_net_debt`.
- `MOIC = exit_equity / sponsor_equity`.
- `IRR = MOIC^(1/hold_years) − 1` — still closed-form; a single exit cash flow, no interim
  distributions.

## Sensitivity grid

Axes remain 2-D: **entry multiple × total leverage**. For a target total leverage `L`, scale
every tranche's `turns` by `L / Σ(base turns)`; rates and `mandatory_amort_pct` are held. The
RBI cap still applies per cell. The existing 5×5 grid stays meaningful.

## Downstream changes

- `src/lbo_model.py` — `run_lbo` rewritten around per-tranche state and the waterfall;
  `sensitivity_grid` updated to scale tranches. Return structure gains per-tranche sources &
  uses and a per-tranche schedule; existing top-level keys (`moic`, `irr`, `exit_equity`,
  etc.) are preserved.
- `src/screener.py` — `unused_debt_capacity_cr` uses `Σ(tranche turns)` instead of the old
  scalar `leverage_multiple`. One-line change.
- `src/app.py` — sources & uses table itemized by tranche; the yearly schedule gains
  per-tranche ending balances (manageable at 2–3 tranches). Sensitivity tear-sheet controls
  unchanged.
- `data/`, `README.md` — README "Paper-LBO assumptions" and "Sources & uses" sections
  updated to describe tranches and the waterfall.

## Testing

Extend `smoke_test.py` to assert:

1. **Default-equivalence** — a single 3.0x senior tranche (no mezz, no amort) reproduces the
   pre-change MOIC/IRR within tolerance.
2. **Sources = uses** — Σ tranche debt + sponsor equity = EV.
3. **Priority invariant** — across the schedule, mezz principal does not fall via sweep while
   senior balance > 0.
4. **Mandatory amort** — senior balance declines by at least the scheduled amort each year
   until retired.
5. **RBI cap** — pushing total leverage above 0.75 × EV / EBITDA caps total debt at 75% of EV
   and scales tranches proportionally.
6. **Returns sanity** — MOIC and IRR are finite and within a plausible band for the default
   case.
7. **App smoke** — both Streamlit views (shortlist, tear sheet) still render via AppTest.

## Phase 2 seam (informational)

The generic tranche list and per-tranche schedule are the structures Phase 2's
three-statement model and a future PIK/fee/rollover layer attach to. Phase 1 should keep the
tranche representation generic (a list of dicts/objects), not hard-code senior/mezz, so those
layers do not require an engine rewrite.
