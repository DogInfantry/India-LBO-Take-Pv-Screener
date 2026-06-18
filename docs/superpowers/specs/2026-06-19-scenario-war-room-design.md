# Scenario War Room — Design Spec
**Date:** 2026-06-19
**Status:** Approved for implementation

## Overview

Add a Bull / Base / Bear scenario comparison to the India LBO Screener. Scenarios are pre-computed in Python at build time and baked into `results.json`. No live backend required — the feature ships entirely within the existing static Next.js / Vercel deployment.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Static vs live | Static (precomputed) | Zero architecture change; reuses run_lbo as-is; Vercel-native |
| Scenario basis | Explicit lever deltas in config.yaml | Transparent assumptions; every input visible; no statistical opacity |
| Levers varied | Revenue growth, EBITDA margin, exit multiple | Operating + valuation levers; leverage fixed (financing decision, not a state of the world) |
| Placement | Dashboard (compact table) + Tearsheet (full panel) | Portfolio-level and company-level views |
| Tearsheet depth | Full P&L bridge: assumptions → financials → returns | Separates a war room from a sensitivity table |

---

## Data Flow

```
config.yaml  [new scenarios: section]
       │
       ▼
analytics.py::scenario_block(inp, cfg)
       │  runs run_lbo() 3× per company
       ▼
build_company_block() → results.json
       │
       ▼
web-app/public/data/results.json
       │
   ┌───┴────────────────────────┐
   ▼                            ▼
WarRoomTable              ScenarioWarRoom
(dashboard /  page)       (tearsheet /t/[ticker])
```

---

## Layer 1 — Config (`config/config.yaml`)

Append a `scenarios` section. Base = zero deltas (existing run_lbo output unchanged). Deltas are in absolute units (pp for rates, turns for multiples).

```yaml
scenarios:
  bull:
    revenue_growth_delta: 0.08    # +8pp above base → ~16% growth
    margin_delta:         0.05    # +5pp above company entry margin
    exit_multiple_delta:  2.0     # +2x above entry multiple
  bear:
    revenue_growth_delta: -0.05   # -5pp below base → ~3% growth
    margin_delta:         -0.05   # -5pp below company entry margin
    exit_multiple_delta:  -2.0    # -2x below entry multiple
```

---

## Layer 2 — Python (`src/analytics.py`)

### New function: `scenario_block(inp, cfg) -> dict`

```
Inputs:
  inp  — company_inputs() output (entry_revenue, entry_ebitda, assumptions, entry_ev, total_leverage)
  cfg  — full config dict

For each scenario in [bull, base, bear]:
  1. Compute scenario revenue_growth = base_growth + delta (base delta = 0)
  2. Compute scenario entry_ebitda   = entry_revenue × (base_margin + margin_delta)
     where base_margin = entry_ebitda / entry_revenue
  3. Compute scenario exit_multiple  = _entry_multiple(inp) + multiple_delta
  4. Call run_lbo(entry_revenue, sc_ebitda, {**assumptions, "revenue_growth": sc_growth},
                  entry_ev=inp["entry_ev"], total_leverage=inp["total_leverage"],
                  exit_multiple=sc_exit_mult)
  5. Extract:
     - assumptions: {revenue_growth, ebitda_margin, exit_multiple}
     - financials:  {revenue, ebitda, fcf}  ← last year of income_statement / cash_flow
     - returns:     {irr, moic, exit_equity}

Returns:
  {"bull": {assumptions, financials, returns},
   "base": {assumptions, financials, returns},
   "bear": {assumptions, financials, returns}}
```

Edge cases:
- `margin_delta` that pushes margin ≤ 0 → clamp `sc_ebitda = max(0, entry_revenue × sc_margin)`
- Non-finite IRR (degenerate bear case) → store as `null`, same pattern as base case today
- Missing `scenarios` key in cfg → `scenario_block` returns `None`; `build_company_block` stores `scenarios: null`

### Changes to `build_company_block(row, cfg)`

Add one key to the returned dict:
```python
"scenarios": scenario_block(inp, cfg)
```

### Changes to `build_results(results_df, cfg, as_of)`

Add `scenario_irrs` to each `Passer` entry:
```python
sc = company_blocks[ticker].get("scenarios")
"scenario_irrs": {
    "bull": sc["bull"]["returns"]["irr"] if sc else None,
    "base": sc["base"]["returns"]["irr"] if sc else None,
    "bear": sc["bear"]["returns"]["irr"] if sc else None,
} if sc else None
```

---

## Layer 3 — TypeScript Types (`web-app/lib/types.ts`)

```typescript
export interface ScenarioAssumptions {
  revenue_growth: number;
  ebitda_margin: number;
  exit_multiple: number;
}
export interface ScenarioFinancials {
  revenue: number;
  ebitda: number;
  fcf: number;
}
export interface ScenarioReturns {
  irr: number | null;
  moic: number | null;
  exit_equity: number;
}
export interface Scenario {
  assumptions: ScenarioAssumptions;
  financials: ScenarioFinancials;
  returns: ScenarioReturns;
}
export interface ScenarioBlock {
  bull: Scenario;
  base: Scenario;
  bear: Scenario;
}
```

**Additions to existing interfaces:**
- `CompanyBlock`: add `scenarios: ScenarioBlock | null`
- `Passer`: add `scenario_irrs: { bull: number | null; base: number | null; bear: number | null } | null`

---

## Layer 4 — React Components

### `web-app/components/tearsheet/ScenarioWarRoom.tsx`

**Props:** `{ scenarios: ScenarioBlock | null }`

**Render:** If `scenarios` is null, render nothing (degenerate company guard).

Layout: three-column table, rows grouped into three sections separated by a faint rule:

| Section | Rows |
|---|---|
| **Assumptions** | Revenue growth (%), EBITDA margin (%), Exit multiple (x) |
| **Financials at exit** | Revenue (₹cr), EBITDA (₹cr), FCF (₹cr) |
| **Returns** | IRR (large, colour-coded), MOIC (x), Exit equity (₹cr) |

Column styling:
- Bull header + IRR: `text-green-600`; cell background: `bg-green-50`
- Bear header + IRR: `text-red-600`; cell background: `bg-red-50`
- Base: neutral

IRR colour thresholds (consistent with existing tearsheet):
- ≥ 20%: green
- 10–19%: neutral/amber
- < 10%: red

No new charts — table is the correct format (pitch-book style).

### `web-app/components/WarRoomTable.tsx`

**Props:** `{ passers: Passer[] }`

**Render:** If no passer has `scenario_irrs`, render nothing.

Layout: compact table.

| Column | Content |
|---|---|
| Company | Ticker + name, linked to `/t/[ticker]` |
| Bull IRR | `scenario_irrs.bull` formatted as % |
| Base IRR | `scenario_irrs.base` formatted as % |
| Bear IRR | `scenario_irrs.bear` formatted as % |

Rows sorted by Base IRR descending (same order as existing leaderboard). Each IRR cell colour-coded using the same thresholds as above. Null IRR renders as `—`.

---

## Layer 5 — Page Wiring

### `web-app/app/t/[ticker]/page.tsx`

Insert `<ScenarioWarRoom scenarios={company.scenarios} />` as a new `<Section>` after the IrrBridge section, before the SensitivityHeatmap section.

### `web-app/app/page.tsx`

Insert `<WarRoomTable passers={passers} />` as a new section after the IrrLeaderboard section, before the IsoFrontier section.

---

## What Is NOT Touched

- `src/lbo_model.py` — no changes
- `src/statements.py` — no changes
- All existing tearsheet components — no changes
- `vercel.json`, `next.config.mjs` — no changes
- GitHub Actions weekly refresh job — picks up `scenario_block()` automatically

---

## Files Changed (summary)

| File | Change type |
|---|---|
| `config/config.yaml` | Add `scenarios:` section |
| `src/analytics.py` | Add `scenario_block()`, update `build_company_block()`, update `build_results()` |
| `web-app/lib/types.ts` | Add 5 new interfaces, extend `CompanyBlock` and `Passer` |
| `web-app/components/tearsheet/ScenarioWarRoom.tsx` | New component |
| `web-app/components/WarRoomTable.tsx` | New component |
| `web-app/app/t/[ticker]/page.tsx` | Wire in `ScenarioWarRoom` |
| `web-app/app/page.tsx` | Wire in `WarRoomTable` |

**Total: 7 files. 2 new components. 0 existing components modified.**

---

## Testing

- `tests/test_analytics.py`: add `test_scenario_block_base_matches_existing()` — verifies base scenario IRR/MOIC matches `run_lbo` direct output
- `tests/test_analytics.py`: add `test_scenario_block_bull_bear_ordering()` — verifies bull IRR > base IRR > bear IRR for a non-degenerate company
- `web-app/components/tearsheet/ScenarioWarRoom.test.tsx`: snapshot test with a fixture ScenarioBlock; verify null renders nothing
- `web-app/components/WarRoomTable.test.tsx`: snapshot test with fixture passers; verify null scenario_irrs renders `—`
