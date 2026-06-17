# Phase 3 — Tear Sheet (`/t/[ticker]`) — Design

**Date:** 2026-06-18
**Branch:** `feat/phase3-tearsheet`
**Status:** Design — pending implementation

## Problem

Phase 2 shipped the dashboard and a **stub** `/t/[ticker]` page (name + headline
KPIs). The `results.json` contract already carries the full per-company depth
(three statements, per-tranche debt schedule, IRR & value bridges, 5,000-sample
Monte Carlo, downside risk, all three solvers, delisting, feasibility) — but
nothing renders it. Phase 3 builds the real tear sheet: a deep, single-company
research report. It also adds the one piece the contract lacks — a 2D
premium×exit sensitivity grid — for the signature heatmap.

This is Phase 3 of the parent spec (`2026-06-17-lbo-quant-showcase-design.md`).
Phase 4 (weekly CI + `vercel.json` repoint) remains separate.

## Decisions (from visual brainstorming)

- **Layout: sectioned report.** A vertical scroll of titled sections (returns →
  risk → sensitivity → model → debt → deal), Midnight theme, consistent with the
  dashboard. Full-width sections so the 3-statement tables and bridges breathe.
- **Sensitivity = 2D heatmap, premium × exit multiple, IRR-colored**, with the
  existing iso-IRR frontier drawn as the 20%-IRR contour through it (one coherent
  panel). Requires a new Python grid function (Part A).
- **Monte Carlo = distribution histogram** of the 5,000 terminal IRR outcomes
  (the contract carries terminal samples, not year-by-year paths, so a
  time-series fan chart is not possible) — hurdle line + shaded CVaR/VaR tail +
  P(beat hurdle).
- **3 statements = plain full-width tables** (IS / CF / BS). No interactive
  common-size toggle in v1 (YAGNI; can add later).

## Part A — Python contract addition (additive, backward-compatible)

- Add `sensitivity_grid_premium_exit(inp, premiums_pct, exit_multiples)` to
  `src/analytics.py`: for each (premium, exit_multiple) pair, price the
  take-private at `entry_ev = market_cap*(1+premium/100)+net_debt` and run
  `run_lbo(..., entry_ev=…, total_leverage=inp["total_leverage"],
  exit_multiple=…)`, collecting IRR. Returns
  `{ premiums_pct: [...], exit_multiples: [...], irr: number[][] }` (rows =
  premiums, cols = exit multiples). Reuses `run_lbo`; no existing math changes.
- Wire it into `build_company_block` so `sensitivity = { iso_frontier, grid }`.
  The iso-frontier is unchanged; `grid` is new. Degenerate companies keep
  `sensitivity = null`.
- Re-export `web-app/public/data/results.json` via
  `python tools/export_data.py --no-fetch`.
- Axes: `premiums_pct` from `cfg["sensitivity"]`; `exit_multiples` **derived per
  company** as `[entry_multiple−2 … entry_multiple+2]` (5 steps) — the same range
  `iso_irr_frontier` already uses, so the frontier overlay sits naturally on the
  heatmap. No config change needed.

This is the only Python change in Phase 3. It is additive: existing keys are
untouched, so Phase 2's loader/types still parse.

## Part B — Frontend tear sheet (sections, top → bottom)

Replaces the Phase 2 stub at `web-app/app/t/[ticker]/page.tsx`.

1. **Header + summary** — name, ticker, as-of; IRR / MOIC / optimal-exit year
   (from `solvers.optimal_exit.best_year`) / feasibility; Sources & Uses (EV,
   debt tranches, fees, sponsor equity).
2. **Returns attribution** — IRR bridge (deleveraging / EBITDA growth / multiple
   re-rating → total) as a waterfall; value bridge (entry equity → … → exit
   equity, ₹cr) as a waterfall.
3. **Risk** — Monte Carlo IRR histogram (hurdle + CVaR tail shaded); downside
   stat cards (P-beat-hurdle, P-loss, 5% VaR, CVaR on MOIC).
4. **Sensitivity** — premium×exit IRR heatmap with the iso-frontier contour;
   Sobol total-order drivers.
5. **Operating model** — IS / CF / BS as full-width tables. Note the shapes
   differ: IS and CF carry years 1–5 (5 rows); the **balance sheet carries years
   0–5** (6 rows — year 0 is the opening balance). `StatementTable` takes the
   rows + a `startYear` (0 or 1) so it handles both.
6. **Debt** — per-tranche paydown waterfall (senior/mezzanine/revolver over the
   hold) + the debt schedule table + the debt-capacity solver result (max
   leverage, binding coverage).
7. **Deal / take-private** — delisting model (indicative: threshold, float to
   tender, indicative discovered EV, with its stated assumptions) + max-bid
   solver (or "cannot clear hurdle at any premium" when not converged) +
   feasibility component breakdown.

**Degenerate state (e.g. JUSTDIAL):** `returns.degenerate === true` →
`statements/debt_schedule/montecarlo/downside/sensitivity/solvers/sobol` are
`null`. The page renders a clear "n.m. — net cash > market cap; LBO not
computable" banner and shows only the **Deal** section (feasibility + delisting
are non-null). The LBO sections are omitted, not blank.

## Components / file structure

```
web-app/
  app/t/[ticker]/page.tsx          # full tear sheet (replaces stub)
  components/tearsheet/
    Summary.tsx  SourcesUses.tsx
    IrrBridge.tsx  ValueBridge.tsx       # waterfalls (EChart)
    McHistogram.tsx  StatCards.tsx       # risk
    SensitivityHeatmap.tsx  SobolDrivers (reuse)
    StatementTable.tsx                   # IS/CF/BS table (presentational)
    DebtWaterfall.tsx  DebtSchedule.tsx  DebtCapacityCard.tsx
    DelistingCard.tsx  MaxBidCard.tsx  FeasibilityBreakdown.tsx
    DegenerateNotice.tsx
  lib/charts/
    irrBridge.ts  valueBridge.ts  mcHistogram.ts  heatmap.ts  debtWaterfall.ts
  lib/types.ts                     # extend CompanyBlock: statements rows,
                                    # debt_schedule rows, montecarlo, downside,
                                    # solvers, delisting, sources_uses, sensitivity.grid
```

Pure ECharts option-builders in `lib/charts/` (Vitest-tested); presentational
table/card components in `components/tearsheet/`. The page is a server component
that loads the contract and passes typed slices to each section; chart leaves are
`"use client"` (reusing the existing `EChart` wrapper + Midnight theme).

### Types

Phase 2 typed only the dashboard slices. Phase 3 fills in the `CompanyBlock`
detail types: `IncomeRow`/`CashFlowRow`/`BalanceRow`, `DebtScheduleRow`,
`MonteCarlo { irr:(number|null)[]; moic:(number|null)[]; p_beat_hurdle:number }`,
`Downside`, `Solvers { max_bid; debt_capacity; optimal_exit }`, `Delisting`,
`SourcesUses`, and `sensitivity.grid`. All nullable where the engine emits null.

## Data flow / error handling

- The page reads `companies[ticker]` from the build-time loader. Unknown ticker →
  a "not found" message (the stub already does this).
- A degenerate company short-circuits to the DegenerateNotice + Deal section.
- Chart builders receive already-typed, non-null slices (the page guards nulls
  before rendering a section), so a builder never sees null.

## Testing / verification

- **Python:** unit test for `sensitivity_grid_premium_exit` — grid shape matches
  `len(premiums) × len(exit_multiples)`; IRR decreases along the premium axis
  (more expensive entry → lower IRR) for a healthy name; values reconcile with a
  direct `run_lbo` at a sampled cell. Existing analytics/parity tests stay green.
- **Vitest:** each new option-builder (irrBridge, valueBridge, mcHistogram,
  heatmap, debtWaterfall) tested on representative data; `StatementTable` mapping
  tested; degenerate company yields the notice (page-level smoke via the loader).
- **Build gate:** `npm run build` (static export) succeeds; `/t/[ticker]`
  pre-renders for every passer including the degenerate one.
- **Visual:** dev server + preview screenshots of a healthy tear sheet
  (NATCOPHARM) and the degenerate one (JUSTDIAL), shared back.

## Non-goals (Phase 4 / later)

- `vercel.json` repoint and weekly CI (Phase 4) — until then the old `web/` is
  the deployed site; Phase 3 is built/previewed locally.
- Interactive common-size toggle on the statements; client-side what-if sliders.
- Any new Python beyond the single sensitivity-grid function.

## Risks / open questions

- **Exit-multiple axis for the grid:** RESOLVED — derived per company as
  `[entry_multiple−2 … entry_multiple+2]` (5 steps), no config change, matching
  the iso-frontier range. Grid is ≈5×5 so the weekly export stays fast.
- **results.json size:** adding a 5×5 grid per company is negligible (~25 floats
  × 6 names). No per-ticker split needed.
- **Tear-sheet page size:** many chart leaves on one route — all hydrate from
  inlined props; confirm the static export bundle stays reasonable (it will;
  ECharts is shared across leaves).
```
