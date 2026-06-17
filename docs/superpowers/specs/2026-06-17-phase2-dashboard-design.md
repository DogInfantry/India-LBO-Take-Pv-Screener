# Phase 2 — Dashboard (Next.js) — Design

**Date:** 2026-06-17
**Branch:** `feat/phase2-dashboard`
**Status:** Design — pending implementation

## Problem

Phase 1 froze the `results.json` contract and the Python engine that emits it,
but nothing renders it. The current deployed site is the old Jinja+Vega static
export, which reads "basic." Phase 2 builds the **dashboard landing page** of the
new Next.js app — the first thing that makes the project look like the premium
reference sites — reading the Phase 1 contract.

This is the second of four phases from the parent spec
(`2026-06-17-lbo-quant-showcase-design.md`). Phase 3 (tear sheet) and Phase 4
(weekly CI) are separate.

## Decisions (from visual brainstorming)

- **Layout: dense grid.** A KPI band across the top, then a multi-panel grid
  (IRR leaderboard, premium×exit heatmap, feasibility, Sobol drivers) — all
  visible at once, Bloomberg-terminal density, minimal scrolling.
- **Theme: "Midnight terminal."** Deep blue-black ground (`#0b0f17`), panel
  `#121826`, emerald accent (`#34d399`) for returns, violet (`#a78bfa`) for
  feasibility/Sobol, amber/red for the heatmap warm end, muted slate text,
  monospace labels. High contrast so the quant charts pop.
- **Stack: Next.js (App Router, `output: 'export'`) + Tailwind + ECharts**
  (via `echarts-for-react`), TypeScript.

## Scope (Phase 2 only)

- The dashboard route `/`: KPI band + the four dense-grid panels.
- A reusable themed `EChart` wrapper + the Midnight design tokens.
- A typed, build-time loader for `results.json` and TypeScript types mirroring
  the Phase 1 contract.
- A **minimal `/t/[ticker]` stub** page (company name + headline KPIs,
  `generateStaticParams` from the passer list) so leaderboard links resolve and
  the static export is valid. The full tear sheet is Phase 3.
- Visual verification via the preview tooling (dev server + screenshot).

## Non-goals (deferred to Phase 3 / 4)

- The full tear sheet: 3-statements, debt-paydown waterfall, IRR & value
  bridges, Monte Carlo fan chart, downside/CVaR, solver panels, delisting.
- Any client-side recomputation — the frontend only reads precomputed numbers.
- Weekly CI automation (`weekly.yml`) and the `vercel.json` repoint to build
  `web-app/` (Phase 4 — until then the existing `web/` site stays the deployed
  one; Phase 2 is developed/previewed locally).
- No changes to any Python (`src/`, `tools/`) — Phase 2 is frontend only.

## Architecture

```
web-app/public/data/results.json   (emitted by Phase 1 tools/export_data.py)
            │  read at BUILD time (server component + fs), typed
            ▼
   lib/data.ts  ── parses & validates ──►  lib/types.ts  (contract types)
            │
            ▼
   app/page.tsx (dashboard, server component)
        └─ <KpiBand> <IrrLeaderboard> <SensitivityHeatmap>
           <FeasibilityPanel> <SobolDrivers>   (each takes typed props)
                         │ all charts go through
                         ▼
                   components/EChart.tsx  (Midnight theme baked in)
            │
            ▼
   next build (output: 'export')  ──►  static HTML/JS  ──►  Vercel CDN
```

No Python runs on Vercel; no runtime data fetch — the JSON is inlined at build.

## Components / file structure

```
web-app/
  package.json, next.config.mjs (output:'export'), tsconfig.json
  tailwind.config.ts            # Midnight tokens (colors, mono/sans fonts)
  app/
    layout.tsx                  # html shell, fonts, global bg
    globals.css                 # Tailwind layers + base theme vars
    page.tsx                    # dashboard (server component)
    t/[ticker]/page.tsx         # stub tear sheet (generateStaticParams)
  components/
    EChart.tsx                  # themed echarts-for-react wrapper
    KpiBand.tsx
    IrrLeaderboard.tsx          # bars; dims degenerate -> "n.m."; row -> /t/[ticker]
    SensitivityHeatmap.tsx      # premium x exit heatmap (top name)
    FeasibilityPanel.tsx        # ranked feasibility (violet)
    SobolDrivers.tsx            # variance-share bars
  lib/
    types.ts                    # Results, Passer, CompanyBlock (mirror COMPANY_KEYS)
    data.ts                     # loadResults(): reads public/data/results.json at build
  public/data/results.json      # gitignored build artifact (from Phase 1)
```

Each component has one responsibility, takes typed props, and renders from data
only (no fetching inside components — the page passes data down). The `EChart`
wrapper is the single place the theme is enforced, so charts can't drift.

### Contract types (`lib/types.ts`)

TypeScript interfaces mirroring the Phase 1 JSON: `Results { as_of, config,
universe, passers: Passer[], companies: Record<string, CompanyBlock> }`,
`Passer { ticker, name, irr, moic, degenerate, feasibility, max_bid_premium_pct }`,
and a `CompanyBlock` covering the 13 `COMPANY_KEYS` (returns, montecarlo,
downside, sensitivity, solvers, sobol, feasibility, delisting, statements,
debt_schedule, sources_uses) with **nullable** fields where Phase 1 emits
`null` (degenerate names, NaN→null). Phase 2 only consumes the dashboard-level
slices; the rest are typed now so Phase 3 inherits them.

### Degenerate handling

`IrrLeaderboard` and `KpiBand` read `passer.degenerate` / `returns.degenerate`:
degenerate names render dimmed with "n.m." and are excluded from "top IRR/MOIC"
aggregates — mirroring the Phase 1 engine and the existing site's JUSTDIAL fix.

## Data flow / error handling

- `loadResults()` runs at build in a server component, reads the JSON with `fs`,
  and throws a clear error if the file is missing or fails a shape check (so a
  bad/empty contract fails the build loudly rather than rendering blank panels).
- Aggregates (top IRR, top MOIC) are computed from the non-degenerate passers in
  the loader/page, not in chart components.

## Testing / verification

- **Build gate:** `next build` (static export) must succeed — this is the
  primary correctness gate and fails if the contract is missing/malformed or
  types don't match.
- **Vitest unit test** on `lib/data.ts`: against the real `results.json`,
  asserts every `passer.ticker` has a `companies[ticker]` block, top-IRR
  excludes degenerate names, and types parse. (Vitest is the chosen JS test
  tool.)
- **Visual verification:** run the dev server via the preview tooling, snapshot
  the dashboard, and confirm panels render with real data + the Midnight theme —
  shared back as a screenshot, not asserted by hand.

## Risks / open questions

- **results.json availability for build/test:** Phase 1 gitignores the generated
  file. Phase 2's build and Vitest need it present — the dev/build workflow runs
  `python tools/export_data.py --no-fetch` first (documented in the web-app
  README). CI wiring is Phase 4; locally it's a documented prerequisite.
- **ECharts SSR:** `echarts-for-react` is client-side; chart components are
  client components (`"use client"`) fed by server-loaded data. The page stays a
  server component; only the chart leaves are client. Confirm static export emits
  them correctly (it does — they hydrate from inlined props).
- **Fonts:** reuse the repo's existing Inter for body; pick one mono (e.g.
  JetBrains Mono or `ui-monospace`) for labels — finalized in the plan.
```
