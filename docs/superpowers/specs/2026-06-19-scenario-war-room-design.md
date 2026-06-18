# Scenario War Room — Design Spec
**Date:** 2026-06-19
**Status:** Revised after spec review (v2)

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
  1. Compute sc_growth       = base_growth + revenue_growth_delta  (base delta = 0)
  2. Compute sc_margin       = base_margin + margin_delta          (base_margin = entry_ebitda / entry_revenue)
  3. Compute sc_ebitda       = entry_revenue × sc_margin           (entry_revenue is ALWAYS the as-of-today value
                                                                     from inp; it does NOT vary across scenarios)
  4. Compute sc_exit_mult    = _entry_multiple(inp) + exit_multiple_delta
  5. Clamp: sc_ebitda = max(0.0, sc_ebitda)
  6. If sc_ebitda == 0 after clamping, skip run_lbo and store this scenario entry as null.
  7. Call run_lbo(inp["entry_revenue"], sc_ebitda,
                  {**assumptions, "revenue_growth": sc_growth},
                  entry_ev=inp["entry_ev"],
                  total_leverage=inp["total_leverage"],
                  exit_multiple=sc_exit_mult)
  8. Extract:
     - assumptions: {revenue_growth: sc_growth,
                     ebitda_margin:  sc_ebitda / entry_revenue,  ← absolute margin, not delta
                     exit_multiple:  sc_exit_mult}
     - financials:  {revenue: income_statement[-1]["revenue"],
                     ebitda:  income_statement[-1]["ebitda"],
                     fcf_for_debt: cash_flow[-1]["fcf_for_debt"]}  ← key name from run_lbo output
     - returns:     {irr:         None if not finite else res["irr"],
                     moic:        None if not finite else res["moic"],  ← moic also needs isfinite guard
                     exit_equity: res["exit_equity"]}

Returns:
  {"bull": {assumptions, financials, returns},   # null if sc_ebitda clamped to 0
   "base": {assumptions, financials, returns},
   "bear": {assumptions, financials, returns}}   # null if sc_ebitda clamped to 0
```

Edge cases:
- `sc_ebitda == 0` after clamping → skip `run_lbo`, store that scenario entry as `null` (consistent with degenerate base handling)
- Non-finite `irr` or `moic` from `run_lbo` (can return `float("nan")`) → apply `isfinite` guard, store as `null`
- Missing `scenarios` key in cfg → `scenario_block` returns `None`; `build_company_block` stores `"scenarios": None`

### Changes to `build_company_block(row, cfg)`

Add one key to the non-degenerate returned dict:
```python
"scenarios": scenario_block(inp, cfg)
```

Also add `"scenarios": None` to the **degenerate early-return stub** (the block that exits early for net-cash / negative-EV companies). All keys on CompanyBlock must be present in both paths.

Add `"scenarios"` to the `COMPANY_KEYS` module-level list in `analytics.py` (consistency with existing convention).

### Changes to `build_results(results_df, cfg, as_of)`

Add `scenario_irrs` to each `Passer` entry. Guard against both a null `scenarios` block (degenerate company) AND a null individual scenario (sc_ebitda clamped to zero):
```python
sc = company_blocks[ticker].get("scenarios")

def _sc_irr(sc, name):
    if not sc:
        return None
    s = sc.get(name)          # s is Scenario dict or None
    return s["returns"]["irr"] if s else None

"scenario_irrs": {
    "bull": _sc_irr(sc, "bull"),
    "base": _sc_irr(sc, "base"),
    "bear": _sc_irr(sc, "bear"),
}
```

---

## Layer 3 — TypeScript Types (`web-app/lib/types.ts`)

```typescript
export interface ScenarioAssumptions {
  revenue_growth: number;
  ebitda_margin: number;   // absolute margin (e.g. 0.22), NOT the delta
  exit_multiple: number;
}
export interface ScenarioFinancials {
  revenue: number;
  ebitda: number;
  fcf_for_debt: number;    // matches run_lbo cash_flow key — displayed as "FCF" in UI
}
export interface ScenarioReturns {
  irr: number | null;      // null when non-finite (degenerate scenario)
  moic: number | null;     // null when non-finite (same guard as irr)
  exit_equity: number;
}
export interface Scenario {
  assumptions: ScenarioAssumptions;
  financials: ScenarioFinancials;
  returns: ScenarioReturns;
}
export interface ScenarioBlock {
  bull: Scenario | null;   // null when sc_ebitda clamped to zero for this scenario
  base: Scenario | null;
  bear: Scenario | null;
}
```

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

Column styling — two independent rules:
- **Column headers** (Bull / Base / Bear labels): always static colour — Bull header `text-green-600`, Bear header `text-red-600`, Base neutral. These never change regardless of IRR value.
- **IRR value cell**: threshold-driven colour applied to the IRR number itself only:
  - ≥ 20%: `text-green-600`
  - 10–19%: neutral / amber
  - < 10%: `text-red-600`
- **Cell backgrounds**: Bull column `bg-green-50`, Bear column `bg-red-50`, Base neutral. Static, not threshold-driven.

Example: a bull scenario that produces 8% IRR → bull column header stays green, cell background stays green-50, but the IRR number itself renders red.

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

- `tests/test_analytics.py`: `test_scenario_block_base_matches_existing()` — verifies base scenario `irr`, `moic`, and `financials.revenue` each match `run_lbo` direct output (catches accidental `revenue_growth` contamination between scenarios)
- `tests/test_analytics.py`: `test_scenario_block_bull_bear_ordering()` — verifies bull IRR > base IRR > bear IRR for a non-degenerate company
- `tests/test_analytics.py`: `test_scenario_block_zero_ebitda_clamp()` — verifies that a margin_delta large enough to zero sc_ebitda returns `null` for that scenario rather than crashing
- `web-app/components/tearsheet/ScenarioWarRoom.test.tsx`: snapshot with fixture `ScenarioBlock`; verify null prop renders nothing; verify `fcf_for_debt` field is read (not `fcf`)
- `web-app/components/WarRoomTable.test.tsx`: snapshot with fixture passers; verify null `scenario_irrs` renders `—`
