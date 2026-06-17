# Phase 3 — Tear Sheet (`/t/[ticker]`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full single-company tear sheet at `/t/[ticker]` — a sectioned research report (returns → risk → sensitivity → model → debt → deal) rendering the contract's per-company depth — plus one additive Python function that adds a premium×exit IRR grid for the sensitivity heatmap.

**Architecture:** Part A adds `sensitivity_grid_premium_exit` to `src/analytics.py`, wires it into `build_company_block` (`sensitivity = { iso_frontier, grid }`), and re-exports `results.json` — additive, no existing math touched. Part B replaces the Phase 2 stub page with sectioned components: pure Vitest-tested ECharts option-builders in `lib/charts/` (following the existing Phase 2 pattern) plus presentational table/card components; the page (server component) loads the contract and passes typed, null-guarded slices to each section.

**Tech Stack:** Python 3.14 + pytest (Part A); Next.js 15 / React 19 / TypeScript / ECharts 5 / Vitest (Part B). Reuses the Phase 2 `EChart` wrapper and `MIDNIGHT` theme.

---

## Reference: shapes (verified against `web-app/public/data/results.json`)

- `statements.income[]`: `{year(1..5), revenue, ebitda, da, dfc_amort, ebit, interest, ebt, taxes, net_income}`
- `statements.cash_flow[]`: `{year(1..5), net_income, da, delta_nwc, cfo, capex, fcf_for_debt, principal_repaid, revolver_draw, cff, ending_cash}`
- `statements.balance_sheet[]`: `{year(0..5), cash, ar, inventory, ap, nwc, ppe, goodwill, dfc, assets, debt, equity, balance_error}` — **6 rows (year 0 = opening)**
- `debt_schedule[]`: `{year(1..5), ebitda, interest, ..., revolver, cash, senior_repaid, senior_ending, mezzanine_repaid, mezzanine_ending, ending_debt}`
- `sources_uses`: `{enterprise_value, debt, tranches:[{name, amount, pct_of_ev}], txn_fees, financing_fees, sponsor_equity, debt_pct_of_ev}`
- `returns.irr_bridge`: `{deleveraging, ebitda_growth, multiple_rerating, total_irr}`
- `returns.value_bridge`: `{entry_equity, ebitda_growth, multiple_change, debt_paydown, fees_and_other, exit_equity}`
- `montecarlo`: `{irr:(number|null)[5000], moic:(number|null)[5000], p_beat_hurdle, params}`
- `downside`: `{p_loss, var5_moic, cvar5_moic}`
- `solvers`: `{max_bid:{converged, reason, max_premium_pct, max_ev}, debt_capacity:{converged, max_leverage, min_coverage_at_max}, optimal_exit:{by_year:[{year,irr,moic}], best_year}}`
- `sobol.total_order`: `{revenue_growth, ebitda_shock, exit_multiple}`
- `delisting`: `{indicative, acceptance_threshold_pct, promoter_holding_pct, float_to_tender_pct, indicative_premium_pct, indicative_discovered_ev_cr, assumptions}`
- `feasibility`: `{score, components, weights}`
- `sensitivity` (current): `{iso_frontier:{target_irr, points:[{exit_multiple, premium_pct}]}}` → Part A adds `grid`.
- Degenerate company (JUSTDIAL): `statements/debt_schedule/montecarlo/downside/sensitivity/solvers/sobol = null`; `sources_uses/feasibility/delisting` non-null; `returns.degenerate=true, irr/moic=null`.

## Reference: existing patterns to mirror

- Python sweep pattern: `iso_irr_frontier` in `src/analytics.py` (premium → run_lbo at `entry_ev = market_cap*(1+p/100)+net_debt`).
- TS chart builder pattern: `web-app/lib/charts/frontier.ts` (pure fn → `EChartsOption`, spreads `baseOption`, uses `MIDNIGHT`). Component wrapper: `web-app/components/IsoFrontier.tsx`.
- `company_inputs(row, cfg)` returns `entry_revenue, entry_ebitda, assumptions, market_cap, net_debt, premium_pct, total_leverage, entry_ev`. `_entry_multiple(inp)` = `entry_ev/entry_ebitda`.

## File structure

```
src/analytics.py                         # + sensitivity_grid_premium_exit; build_company_block sensitivity = {iso_frontier, grid}
tests/test_analytics.py                  # + grid tests
web-app/
  lib/types.ts                           # + detail types + sensitivity.grid
  lib/company.ts                         # loadCompany(ticker) typed accessor
  lib/charts/ irrBridge.ts valueBridge.ts mcHistogram.ts heatmap.ts debtWaterfall.ts
  lib/format.ts                          # pct/x/cr formatters (shared)
  components/tearsheet/
    Summary.tsx SourcesUses.tsx IrrBridge.tsx ValueBridge.tsx McHistogram.tsx
    StatCards.tsx SensitivityHeatmap.tsx StatementTable.tsx DebtWaterfall.tsx
    DebtSchedule.tsx SolverCards.tsx DelistingCard.tsx FeasibilityBreakdown.tsx
    DegenerateNotice.tsx Section.tsx
  app/t/[ticker]/page.tsx                # full tear sheet (replaces stub)
```

---

## PART A — Python: premium×exit sensitivity grid

### Task 1: `sensitivity_grid_premium_exit`

**Files:** Modify `src/analytics.py`; Test `tests/test_analytics.py`.

- [ ] **Step 1: Failing test**

```python
def test_sensitivity_grid_premium_exit_shape_and_monotonicity():
    cfg = base_cfg(); inp = analytics.company_inputs(sample_row(), cfg)
    premiums = [0.0, 10.0, 20.0, 30.0]
    em = inp["entry_ev"] / inp["entry_ebitda"]
    exits = [round(em - 1, 1), round(em, 1), round(em + 1, 1)]
    g = analytics.sensitivity_grid_premium_exit(inp, premiums, exits)
    assert g["premiums_pct"] == premiums
    assert g["exit_multiples"] == exits
    assert len(g["irr"]) == len(premiums)              # rows = premiums
    assert all(len(row) == len(exits) for row in g["irr"])
    # IRR falls as premium rises (more expensive entry), holding exit fixed
    col0 = [g["irr"][i][0] for i in range(len(premiums))]
    assert col0[0] > col0[-1]
    # IRR matches a direct run_lbo at a sampled cell
    ev = inp["market_cap"] * (1 + premiums[1] / 100.0) + inp["net_debt"]
    direct = analytics.run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                               entry_ev=ev, total_leverage=inp["total_leverage"],
                               exit_multiple=exits[2])["irr"]
    assert g["irr"][1][2] == pytest.approx(direct, abs=1e-9)
```

- [ ] **Step 2: Run — expect FAIL.** Run: `python -m pytest tests/test_analytics.py -k premium_exit -v`

- [ ] **Step 3: Implement** (append to `src/analytics.py`, near `iso_irr_frontier`)

```python
def sensitivity_grid_premium_exit(inp: dict, premiums_pct: list[float],
                                  exit_multiples: list[float]) -> dict:
    """IRR grid over entry premium (rows) x exit multiple (cols), at base leverage.

    Each cell prices the take-private at entry_ev = market_cap*(1+prem/100)+net_debt
    and exits at the given multiple. The iso_irr_frontier is the target-IRR contour
    through this surface (same axes), so the two render as one panel.
    """
    grid = []
    for prem in premiums_pct:
        ev = inp["market_cap"] * (1 + prem / 100.0) + inp["net_debt"]
        row = []
        for xm in exit_multiples:
            res = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                          entry_ev=ev, total_leverage=inp["total_leverage"],
                          exit_multiple=xm)
            row.append(res["irr"])
        grid.append(row)
    return {"premiums_pct": premiums_pct, "exit_multiples": exit_multiples, "irr": grid}
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(analytics): sensitivity_grid_premium_exit (premium x exit IRR grid)`

---

### Task 2: Wire the grid into the contract + re-export

**Files:** Modify `src/analytics.py` (`build_company_block`); Test `tests/test_analytics.py`.

- [ ] **Step 1: Failing test** (grid present for healthy, sensitivity still null for degenerate)

```python
def test_company_block_sensitivity_has_grid():
    cfg = base_cfg(); block = analytics.build_company_block(sample_row(), cfg)
    assert "iso_frontier" in block["sensitivity"]
    g = block["sensitivity"]["grid"]
    # 5 premiums (config) x 5 exit multiples (entry +/- 2)
    assert len(g["premiums_pct"]) == len(cfg["sensitivity"]["premiums_pct"])
    assert len(g["exit_multiples"]) == 5
    assert len(g["irr"]) == len(g["premiums_pct"])
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** — in `build_company_block`, where `sensitivity` is set for the NON-degenerate branch, replace:

```python
        "sensitivity": {"iso_frontier": iso_irr_frontier(inp)},
```
with:

```python
        "sensitivity": {"iso_frontier": iso_irr_frontier(inp),
                        "grid": sensitivity_grid_premium_exit(
                            inp, cfg["sensitivity"]["premiums_pct"],
                            [round(_entry_multiple(inp) - 2 + i, 1) for i in range(5)])},
```

(The degenerate branch keeps `"sensitivity": None` — do not touch it.)

- [ ] **Step 4: Run — expect PASS.** Then full suite: `python -m pytest -q` (all green, no regressions).

- [ ] **Step 5: Re-export the contract**
Run (repo root): `python tools/export_data.py --no-fetch`
Expected: writes `web-app/public/data/results.json`; spot-check a healthy company now has `companies[t].sensitivity.grid.irr` as a 5×5 array.

- [ ] **Step 6: Commit** `feat(analytics): add premium x exit grid to the sensitivity block`

---

## PART B — Frontend: the tear sheet

### Task 3: Extend types + typed company accessor + formatters

**Files:** Modify `web-app/lib/types.ts`; Create `web-app/lib/company.ts`, `web-app/lib/format.ts`, test `web-app/lib/company.test.ts`.

- [ ] **Step 1: Failing test** (`web-app/lib/company.test.ts`)

```ts
import { it, expect } from "vitest";
import { loadCompany } from "@/lib/company";
import { loadResults } from "@/lib/data";

it("loads a healthy company block with detail fields typed", () => {
  const top = loadResults().passers.find((p) => !p.degenerate)!;
  const co = loadCompany(top.ticker)!;
  expect(co.statements!.income.length).toBe(5);
  expect(co.statements!.balance_sheet.length).toBe(6);   // year 0..5
  expect(co.sensitivity!.grid.irr.length).toBeGreaterThan(0);
  expect(co.solvers!.optimal_exit.best_year).toBeGreaterThanOrEqual(1);
});
it("returns a degenerate block with null LBO sections", () => {
  const d = loadResults().passers.find((p) => p.degenerate)!;
  const co = loadCompany(d.ticker)!;
  expect(co.returns.degenerate).toBe(true);
  expect(co.statements).toBeNull();
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

Extend `web-app/lib/types.ts` — replace the `CompanyBlock` interface's loose `[k: string]: unknown` detail with concrete types:

```ts
export interface IncomeRow { year:number; revenue:number; ebitda:number; da:number;
  dfc_amort:number; ebit:number; interest:number; ebt:number; taxes:number; net_income:number; }
export interface CashFlowRow { year:number; net_income:number; da:number; delta_nwc:number;
  cfo:number; capex:number; fcf_for_debt:number; principal_repaid:number;
  revolver_draw:number; cff:number; ending_cash:number; }
export interface BalanceRow { year:number; cash:number; ar:number; inventory:number; ap:number;
  nwc:number; ppe:number; goodwill:number; dfc:number; assets:number; debt:number;
  equity:number; balance_error:number; }
export interface DebtScheduleRow { year:number; ebitda:number; interest:number; revolver:number;
  cash:number; senior_repaid:number; senior_ending:number; mezzanine_repaid:number;
  mezzanine_ending:number; ending_debt:number; [k:string]:number; }
export interface Tranche { name:string; amount:number; pct_of_ev:number; }
export interface SourcesUses { enterprise_value:number; debt:number; tranches:Tranche[];
  txn_fees:number; financing_fees:number; sponsor_equity:number; debt_pct_of_ev:number; }
export interface IrrBridge { deleveraging:number; ebitda_growth:number;
  multiple_rerating:number; total_irr:number; }
export interface ValueBridge { entry_equity:number; ebitda_growth:number; multiple_change:number;
  debt_paydown:number; fees_and_other:number; exit_equity:number; }
export interface MonteCarlo { irr:(number|null)[]; moic:(number|null)[]; p_beat_hurdle:number; }
export interface Downside { p_loss:number|null; var5_moic:number|null; cvar5_moic:number|null; }
export interface Solvers {
  max_bid:{ converged:boolean; reason?:string; max_premium_pct:number|null; max_ev:number|null };
  debt_capacity:{ converged:boolean; max_leverage:number|null; min_coverage_at_max:number|null };
  optimal_exit:{ by_year:{year:number; irr:number|null; moic:number|null}[]; best_year:number|null };
}
export interface Delisting { indicative:boolean; acceptance_threshold_pct:number;
  promoter_holding_pct:number; float_to_tender_pct:number; indicative_premium_pct:number;
  indicative_discovered_ev_cr:number; assumptions:string; }
export interface SensitivityGrid { premiums_pct:number[]; exit_multiples:number[]; irr:(number|null)[][]; }
```
and update `CompanyBlock` so these fields are typed and nullable:
```ts
export interface CompanyBlock {
  ticker:string; name:string;
  statements: { income:IncomeRow[]; cash_flow:CashFlowRow[]; balance_sheet:BalanceRow[] } | null;
  debt_schedule: DebtScheduleRow[] | null;
  sources_uses: SourcesUses;
  returns: { irr:number|null; moic:number|null; degenerate:boolean;
             irr_bridge:IrrBridge|null; value_bridge:ValueBridge|null };
  montecarlo: MonteCarlo | null;
  downside: Downside | null;
  sensitivity: { iso_frontier:{target_irr:number; points:IsoFrontierPoint[]}; grid:SensitivityGrid } | null;
  solvers: Solvers | null;
  sobol: { first_order:Record<string,number>; total_order:Record<string,number> } | null;
  feasibility: { score:number; components:Record<string,number>; weights:Record<string,number> };
  delisting: Delisting;
}
```

`web-app/lib/company.ts`:
```ts
import { loadResults } from "./data";
import type { CompanyBlock } from "./types";
export function loadCompany(ticker: string): CompanyBlock | null {
  return loadResults().companies[ticker] ?? null;
}
```

`web-app/lib/format.ts`:
```ts
export const pct = (v:number|null|undefined, d=1) => v==null ? "n.m." : `${(v*100).toFixed(d)}%`;
export const mult = (v:number|null|undefined, d=2) => v==null ? "n.m." : `${v.toFixed(d)}x`;
export const cr = (v:number|null|undefined) => v==null ? "—" : `₹${Math.round(v).toLocaleString("en-IN")} cr`;
```

- [ ] **Step 4: Run — expect PASS** (`npm run test` from `web-app/`).
- [ ] **Step 5: Commit** `feat(web): tear-sheet contract types + company accessor + formatters`

---

### Task 4: IRR bridge waterfall

**Files:** Create `web-app/lib/charts/irrBridge.ts`, `web-app/components/tearsheet/IrrBridge.tsx`, test `web-app/lib/charts/irrBridge.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { it, expect } from "vitest";
import { buildIrrBridgeOption } from "@/lib/charts/irrBridge";
const br = { deleveraging:0.056, ebitda_growth:0.101, multiple_rerating:0.0, total_irr:0.157 };
it("renders a 4-bar cumulative waterfall ending at total IRR", () => {
  const o:any = buildIrrBridgeOption(br);
  expect(o.xAxis.data).toEqual(["Deleveraging","EBITDA growth","Multiple re-rating","Total IRR"]);
  // floating bars: base (transparent) + visible stack; last bar is the full total
  const vis = o.series.find((s:any)=>s.name==="value").data;
  expect(vis[vis.length-1]).toBeCloseTo(0.157);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** (floating-bar waterfall: a transparent `base` series + a visible `value` series)

```ts
import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { IrrBridge } from "@/lib/types";

export function buildIrrBridgeOption(b: IrrBridge): EChartsOption {
  const steps = [b.deleveraging, b.ebitda_growth, b.multiple_rerating];
  const cats = ["Deleveraging","EBITDA growth","Multiple re-rating","Total IRR"];
  const base:number[] = []; const val:number[] = []; let run = 0;
  for (const s of steps) { base.push(Math.min(run, run+s)); val.push(Math.abs(s)); run += s; }
  base.push(0); val.push(b.total_irr);                       // final total from zero
  return {
    ...baseOption,
    tooltip: { ...baseOption.tooltip, trigger:"axis",
      formatter:(ps:any)=>`${ps[0].axisValue}: ${((ps.find((p:any)=>p.seriesName==="value")?.value??0)*100).toFixed(1)}%` },
    xAxis: { type:"category", data:cats, axisLabel:{ color:MIDNIGHT.muted, fontSize:9, interval:0 } },
    yAxis: { type:"value", axisLabel:{ color:MIDNIGHT.axis, formatter:(v:number)=>`${(v*100)|0}%` },
             splitLine:{ lineStyle:{ color:MIDNIGHT.edge } } },
    series: [
      { name:"base", type:"bar", stack:"t", itemStyle:{ color:"transparent" }, data:base },
      { name:"value", type:"bar", stack:"t",
        itemStyle:{ color:(p:any)=> p.dataIndex===3 ? MIDNIGHT.emerald : MIDNIGHT.emeraldDk,
                    borderRadius:[2,2,0,0] }, data:val },
    ],
  };
}
```

`web-app/components/tearsheet/IrrBridge.tsx`:
```tsx
"use client";
import { buildIrrBridgeOption } from "@/lib/charts/irrBridge";
import { EChart } from "@/components/EChart";
import type { IrrBridge as T } from "@/lib/types";
export function IrrBridge({ bridge }: { bridge: T }) {
  return <EChart option={buildIrrBridgeOption(bridge)} height={200} />;
}
```

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): IRR bridge waterfall`

---

### Task 5: Value bridge waterfall (₹cr)

**Files:** Create `web-app/lib/charts/valueBridge.ts`, `web-app/components/tearsheet/ValueBridge.tsx`, test.

- [ ] **Step 1: Failing test**

```ts
import { it, expect } from "vitest";
import { buildValueBridgeOption } from "@/lib/charts/valueBridge";
const vb = { entry_equity:8000, ebitda_growth:5000, multiple_change:0, debt_paydown:3000,
             fees_and_other:-200, exit_equity:15800 };
it("starts at entry equity and ends at exit equity", () => {
  const o:any = buildValueBridgeOption(vb);
  expect(o.xAxis.data[0]).toBe("Entry equity");
  expect(o.xAxis.data[o.xAxis.data.length-1]).toBe("Exit equity");
  const val = o.series.find((s:any)=>s.name==="value").data;
  expect(val[0]).toBeCloseTo(8000);
  expect(val[val.length-1]).toBeCloseTo(15800);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** (anchored waterfall: first bar = entry equity from 0, middle = deltas, last = exit equity from 0)

```ts
import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { ValueBridge } from "@/lib/types";

export function buildValueBridgeOption(b: ValueBridge): EChartsOption {
  const deltas = [
    ["EBITDA growth", b.ebitda_growth], ["Multiple", b.multiple_change],
    ["Debt paydown", b.debt_paydown], ["Fees/other", b.fees_and_other],
  ] as [string,number][];
  const cats = ["Entry equity", ...deltas.map(d=>d[0]), "Exit equity"];
  const base:number[] = [0]; const val:number[] = [b.entry_equity]; let run = b.entry_equity;
  for (const [,d] of deltas) { base.push(Math.min(run, run+d)); val.push(Math.abs(d)); run += d; }
  base.push(0); val.push(b.exit_equity);
  return {
    ...baseOption,
    tooltip: { ...baseOption.tooltip, trigger:"axis" },
    xAxis: { type:"category", data:cats, axisLabel:{ color:MIDNIGHT.muted, fontSize:9, interval:0, rotate:20 } },
    yAxis: { type:"value", axisLabel:{ color:MIDNIGHT.axis }, splitLine:{ lineStyle:{ color:MIDNIGHT.edge } } },
    series: [
      { name:"base", type:"bar", stack:"v", itemStyle:{ color:"transparent" }, data:base },
      { name:"value", type:"bar", stack:"v", data:val,
        itemStyle:{ color:(p:any)=> (p.dataIndex===0||p.dataIndex===cats.length-1)
          ? MIDNIGHT.emerald : (deltas[p.dataIndex-1]?.[1] ?? 0) >= 0 ? MIDNIGHT.emeraldDk : MIDNIGHT.danger,
          borderRadius:[2,2,0,0] } },
    ],
  };
}
```

Component `ValueBridge.tsx` mirrors `IrrBridge.tsx` (takes `bridge: ValueBridge`).

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): value bridge waterfall`

---

### Task 6: Monte Carlo histogram

**Files:** Create `web-app/lib/charts/mcHistogram.ts`, `web-app/components/tearsheet/McHistogram.tsx`, test.

- [ ] **Step 1: Failing test**

```ts
import { it, expect } from "vitest";
import { buildMcHistogramOption } from "@/lib/charts/mcHistogram";
const irr = Array.from({length:1000},(_,i)=> (i%40)/100);   // 0..0.39 spread
it("bins the samples and marks the hurdle", () => {
  const o:any = buildMcHistogramOption(irr.filter(x=>x!=null) as number[], 0.20, 20);
  const counts = o.series[0].data as any[];
  expect(counts.length).toBe(20);
  const total = counts.reduce((a:number,c:any)=> a + (Array.isArray(c)?c[1]:c.value??c), 0);
  expect(total).toBe(1000);
  expect(JSON.stringify(o.series[0].markLine)).toContain("0.2");
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** (fixed-bin histogram; bins below hurdle muted, at/above hurdle emerald)

```ts
import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";

export function buildMcHistogramOption(samples: number[], hurdle: number, bins = 30): EChartsOption {
  const lo = Math.min(...samples), hi = Math.max(...samples);
  const w = (hi - lo) / bins || 1;
  const counts = new Array(bins).fill(0);
  for (const s of samples) counts[Math.min(bins-1, Math.max(0, Math.floor((s-lo)/w)))]++;
  const data = counts.map((c,i)=>({ value:c,
    itemStyle:{ color: (lo + (i+0.5)*w) >= hurdle ? MIDNIGHT.emerald : MIDNIGHT.axis } }));
  return {
    ...baseOption,
    tooltip: { ...baseOption.tooltip, trigger:"axis" },
    xAxis: { type:"category", data:counts.map((_,i)=>`${((lo+i*w)*100).toFixed(0)}%`),
             axisLabel:{ color:MIDNIGHT.axis, interval:Math.floor(bins/6) } },
    yAxis: { type:"value", axisLabel:{ color:MIDNIGHT.axis }, splitLine:{ lineStyle:{ color:MIDNIGHT.edge } } },
    series: [{ type:"bar", data, barWidth:"96%",
      markLine: { silent:true, symbol:"none", lineStyle:{ color:MIDNIGHT.danger, type:"dashed" },
        data:[{ xAxis: Math.round((hurdle-lo)/w) }], label:{ formatter:`hurdle ${(hurdle*100)|0}%`, color:MIDNIGHT.danger } } }],
  };
}
```

`McHistogram.tsx`:
```tsx
"use client";
import { buildMcHistogramOption } from "@/lib/charts/mcHistogram";
import { EChart } from "@/components/EChart";
export function McHistogram({ samples, hurdle }: { samples:(number|null)[]; hurdle:number }) {
  const xs = samples.filter((x):x is number => x!=null);
  return <EChart option={buildMcHistogramOption(xs, hurdle)} height={200} />;
}
```

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): Monte Carlo IRR histogram`

---

### Task 7: Sensitivity heatmap (premium × exit) + frontier overlay

**Files:** Create `web-app/lib/charts/heatmap.ts`, `web-app/components/tearsheet/SensitivityHeatmap.tsx`, test.

- [ ] **Step 1: Failing test**

```ts
import { it, expect } from "vitest";
import { buildHeatmapOption } from "@/lib/charts/heatmap";
const grid = { premiums_pct:[0,10,20], exit_multiples:[6,7,8],
  irr:[[0.30,0.34,0.38],[0.22,0.26,0.30],[0.14,0.18,0.22]] };
const iso = { target_irr:0.2, points:[{exit_multiple:7, premium_pct:14},{exit_multiple:8, premium_pct:21}] };
it("emits one heatmap cell per grid entry + a visualMap + a frontier line series", () => {
  const o:any = buildHeatmapOption(grid, iso, 0.20);
  expect(o.series[0].type).toBe("heatmap");
  expect(o.series[0].data.length).toBe(9);              // 3x3
  expect(o.visualMap).toBeTruthy();
  expect(o.series.some((s:any)=>s.type==="line")).toBe(true);   // frontier overlay
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```ts
import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { SensitivityGrid, IsoFrontierPoint } from "@/lib/types";

export function buildHeatmapOption(
  grid: SensitivityGrid, iso: { target_irr:number; points:IsoFrontierPoint[] }, hurdle: number
): EChartsOption {
  const cells:[number,number,number][] = [];
  let min = Infinity, max = -Infinity;
  grid.irr.forEach((row,r)=> row.forEach((v,c)=>{ if (v!=null){ cells.push([c,r,v]); min=Math.min(min,v); max=Math.max(max,v);} }));
  // frontier points -> [exitIndex(interpolated), premiumIndex] in grid coords
  const xi = (xm:number)=> grid.exit_multiples.reduce((best,e,i)=> Math.abs(e-xm)<Math.abs(grid.exit_multiples[best]-xm)?i:best,0);
  const yi = (pp:number)=> { const idx = grid.premiums_pct.findIndex(p=>p>=pp);
    return idx<=0 ? 0 : idx-1 + (pp-grid.premiums_pct[idx-1])/(grid.premiums_pct[idx]-grid.premiums_pct[idx-1]); };
  const frontier = iso.points.map(p=>[xi(p.exit_multiple), yi(p.premium_pct)]);
  return {
    ...baseOption,
    tooltip: { position:"top", backgroundColor:MIDNIGHT.panel, borderColor:MIDNIGHT.edge,
      textStyle:{ color:MIDNIGHT.ink },
      formatter:(p:any)=> `prem ${grid.premiums_pct[p.value[1]]}% · exit ${grid.exit_multiples[p.value[0]]}x → IRR ${(p.value[2]*100).toFixed(1)}%` },
    grid: { left:48, right:16, top:12, bottom:36 },
    xAxis: { type:"category", data:grid.exit_multiples.map(String), name:"exit ×",
             axisLabel:{ color:MIDNIGHT.axis }, splitArea:{ show:true } },
    yAxis: { type:"category", data:grid.premiums_pct.map(p=>`${p}%`), name:"premium",
             axisLabel:{ color:MIDNIGHT.axis }, splitArea:{ show:true } },
    visualMap: { min, max, calculable:false, orient:"horizontal", left:"center", bottom:0,
      inRange:{ color:["#b91c1c","#ef4444","#fbbf24","#34d399","#059669"] },
      textStyle:{ color:MIDNIGHT.axis }, formatter:(v:number)=>`${(v*100)|0}%` },
    series: [
      { type:"heatmap", data:cells,
        label:{ show:true, color:"#0b0f17", fontSize:9, formatter:(p:any)=>`${(p.value[2]*100).toFixed(0)}` } },
      { type:"line", data:frontier, smooth:true, symbol:"none",
        lineStyle:{ color:MIDNIGHT.ink, width:2, type:"dashed" }, tooltip:{ show:false },
        z:5 },
    ],
  };
}
```

`SensitivityHeatmap.tsx`:
```tsx
"use client";
import { buildHeatmapOption } from "@/lib/charts/heatmap";
import { EChart } from "@/components/EChart";
import type { SensitivityGrid, IsoFrontierPoint } from "@/lib/types";
export function SensitivityHeatmap({ grid, iso, hurdle }:
  { grid:SensitivityGrid; iso:{target_irr:number; points:IsoFrontierPoint[]}; hurdle:number }) {
  return <EChart option={buildHeatmapOption(grid, iso, hurdle)} height={260} />;
}
```

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): premium x exit sensitivity heatmap with frontier overlay`

---

### Task 8: Debt paydown waterfall

**Files:** Create `web-app/lib/charts/debtWaterfall.ts`, `web-app/components/tearsheet/DebtWaterfall.tsx`, test.

- [ ] **Step 1: Failing test**

```ts
import { it, expect } from "vitest";
import { buildDebtWaterfallOption } from "@/lib/charts/debtWaterfall";
import type { DebtScheduleRow } from "@/lib/types";
const sched = [
  { year:1, senior_ending:3000, mezzanine_ending:1700, revolver:0 },
  { year:2, senior_ending:2200, mezzanine_ending:1700, revolver:0 },
] as unknown as DebtScheduleRow[];
it("stacks senior + mezzanine + revolver per year", () => {
  const o:any = buildDebtWaterfallOption(sched);
  const names = o.series.map((s:any)=>s.name);
  expect(names).toEqual(["Senior","Mezzanine","Revolver"]);
  expect(o.xAxis.data).toEqual(["Y1","Y2"]);
  expect(o.series[0].data).toEqual([3000,2200]);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```ts
import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { DebtScheduleRow } from "@/lib/types";

export function buildDebtWaterfallOption(sched: DebtScheduleRow[]): EChartsOption {
  const years = sched.map(r=>`Y${r.year}`);
  const mk = (name:string, key:keyof DebtScheduleRow, color:string) =>
    ({ name, type:"bar", stack:"d", data:sched.map(r=>r[key] as number), itemStyle:{ color } });
  return {
    ...baseOption,
    legend: { textStyle:{ color:MIDNIGHT.muted }, top:0, right:0 },
    tooltip: { ...baseOption.tooltip, trigger:"axis", axisPointer:{ type:"shadow" } },
    xAxis: { type:"category", data:years, axisLabel:{ color:MIDNIGHT.axis } },
    yAxis: { type:"value", axisLabel:{ color:MIDNIGHT.axis }, splitLine:{ lineStyle:{ color:MIDNIGHT.edge } } },
    series: [ mk("Senior","senior_ending",MIDNIGHT.emerald),
              mk("Mezzanine","mezzanine_ending",MIDNIGHT.violet),
              mk("Revolver","revolver",MIDNIGHT.amber) ],
  };
}
```

`DebtWaterfall.tsx` mirrors the other chart components (takes `schedule: DebtScheduleRow[]`).

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): debt paydown waterfall`

---

### Task 9: Presentational components (tables + cards)

**Files:** Create under `web-app/components/tearsheet/`: `Section.tsx`, `StatementTable.tsx`, `StatCards.tsx`, `SourcesUses.tsx`, `DebtSchedule.tsx`, `SolverCards.tsx`, `DelistingCard.tsx`, `FeasibilityBreakdown.tsx`, `DegenerateNotice.tsx`, `Summary.tsx`. Test `web-app/components/tearsheet/StatementTable.test.tsx`.

- [ ] **Step 1: Failing test** (StatementTable is the one with logic — column = year, startYear offset, number formatting)

```tsx
import { it, expect } from "vitest";
import { render } from "@testing-library/react";
import { StatementTable } from "@/components/tearsheet/StatementTable";

it("renders a header per year starting at startYear and a row per line item", () => {
  const rows = [{ year:0, cash:100, debt:5000 }, { year:1, cash:120, debt:4200 }];
  const { getByText, container } = render(
    <StatementTable title="Balance sheet" rows={rows as any}
      lines={[["cash","Cash"],["debt","Debt"]]} startYear={0} />
  );
  getByText("Balance sheet"); getByText("Cash"); getByText("Y0"); getByText("Y1");
  // 1 header row + 2 line rows
  expect(container.querySelectorAll("tbody tr").length).toBe(2);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** (generic, data-driven table; the page supplies which `lines` to show per statement)

`StatementTable.tsx`:
```tsx
import { cr } from "@/lib/format";
export function StatementTable(
  { title, rows, lines, startYear=1 }:
  { title:string; rows:Record<string,number>[]; lines:[string,string][]; startYear?:number }
) {
  const years = rows.map(r=>`Y${r.year ?? ""}`);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-right text-xs font-mono">
        <thead>
          <tr className="text-faint">
            <th className="py-1 text-left font-normal">{title}</th>
            {years.map((y,i)=><th key={i} className="py-1 font-normal">{y}</th>)}
          </tr>
        </thead>
        <tbody>
          {lines.map(([key,label])=>(
            <tr key={key} className="border-t border-edge/50">
              <td className="py-1 text-left text-muted">{label}</td>
              {rows.map((r,i)=><td key={i} className="py-1 text-ink">{cr(r[key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```
> The `startYear` prop is accepted for callers that need it; here year labels come
> straight from each row's `year`, so BS (0..5) and IS/CF (1..5) both render
> correctly without special-casing. Keep the prop for explicitness/legibility.

Implement the remaining components as simple presentational JSX (no logic worth a
unit test — they read fields and format with `lib/format.ts`):
- `Section.tsx` — titled `<section>` wrapper (mono uppercase heading, `border-edge bg-panel` card), reused by every section.
- `StatCards.tsx` — grid of labelled stat tiles; used for downside (P-beat, P-loss, VaR, CVaR) and summary KPIs.
- `SourcesUses.tsx` — EV, each tranche (name + amount + %EV), fees, sponsor equity.
- `DebtSchedule.tsx` — a `StatementTable`-style table of the schedule rows (interest, fcf_for_debt, senior_ending, mezzanine_ending, ending_debt).
- `SolverCards.tsx` — max-bid (premium or "cannot clear hurdle"), debt-capacity (max leverage + binding coverage), optimal-exit (best year).
- `DelistingCard.tsx` — threshold, float to tender, indicative discovered EV, + the `assumptions` string in muted italic.
- `FeasibilityBreakdown.tsx` — score + component sub-scores (holding/pledge/float/valuation) as small bars.
- `DegenerateNotice.tsx` — amber bordered banner: "n.m. — net cash > market cap; LBO not computable."
- `Summary.tsx` — header: name/ticker/as-of + StatCards (IRR/MOIC/optimal-exit/feasibility).

- [ ] **Step 4: Run — expect PASS** (`npm run test`).
- [ ] **Step 5: Commit** `feat(web): tear-sheet tables + cards`

---

### Task 10: Assemble the tear-sheet page

**Files:** Modify `web-app/app/t/[ticker]/page.tsx` (replace the stub).

- [ ] **Step 1: Implement** the sectioned report (server component; `await params` for Next 15)

```tsx
import { loadResults } from "@/lib/data";
import { loadCompany } from "@/lib/company";
import { Section } from "@/components/tearsheet/Section";
import { Summary } from "@/components/tearsheet/Summary";
import { SourcesUses } from "@/components/tearsheet/SourcesUses";
import { IrrBridge } from "@/components/tearsheet/IrrBridge";
import { ValueBridge } from "@/components/tearsheet/ValueBridge";
import { McHistogram } from "@/components/tearsheet/McHistogram";
import { StatCards } from "@/components/tearsheet/StatCards";
import { SensitivityHeatmap } from "@/components/tearsheet/SensitivityHeatmap";
import { SobolDrivers } from "@/components/SobolDrivers";
import { StatementTable } from "@/components/tearsheet/StatementTable";
import { DebtWaterfall } from "@/components/tearsheet/DebtWaterfall";
import { DebtSchedule } from "@/components/tearsheet/DebtSchedule";
import { SolverCards } from "@/components/tearsheet/SolverCards";
import { DelistingCard } from "@/components/tearsheet/DelistingCard";
import { FeasibilityBreakdown } from "@/components/tearsheet/FeasibilityBreakdown";
import { DegenerateNotice } from "@/components/tearsheet/DegenerateNotice";
import { pct, mult } from "@/lib/format";

export function generateStaticParams() {
  return loadResults().passers.map((p) => ({ ticker: p.ticker }));
}

const IS_LINES:[string,string][] = [["revenue","Revenue"],["ebitda","EBITDA"],["ebit","EBIT"],
  ["interest","Interest"],["taxes","Taxes"],["net_income","Net income"]];
const CF_LINES:[string,string][] = [["cfo","CFO"],["capex","Capex"],["fcf_for_debt","FCF for debt"],
  ["principal_repaid","Debt repaid"],["ending_cash","Ending cash"]];
const BS_LINES:[string,string][] = [["cash","Cash"],["nwc","NWC"],["ppe","PP&E"],["goodwill","Goodwill"],
  ["debt","Debt"],["equity","Equity"],["assets","Assets"]];

export default async function TearSheet({ params }: { params: Promise<{ ticker:string }> }) {
  const { ticker } = await params;
  const r = loadResults();
  const co = loadCompany(ticker);
  if (!co) return <main className="p-6 text-muted">Unknown ticker.</main>;
  const hurdle = r.config.hurdle_irr;

  return (
    <main className="mx-auto max-w-5xl p-6 space-y-4">
      <a href="/" className="font-mono text-xs text-faint hover:text-ink">← dashboard</a>
      <Summary co={co} asOf={r.as_of} />

      {co.returns.degenerate ? <DegenerateNotice /> : (
        <>
          <Section title="Returns attribution">
            <div className="grid gap-4 lg:grid-cols-2">
              {co.returns.irr_bridge && <IrrBridge bridge={co.returns.irr_bridge} />}
              {co.returns.value_bridge && <ValueBridge bridge={co.returns.value_bridge} />}
            </div>
          </Section>

          <Section title="Risk — Monte Carlo (5,000 sims)">
            {co.montecarlo && <McHistogram samples={co.montecarlo.irr} hurdle={hurdle} />}
            {co.downside && co.montecarlo &&
              <StatCards tiles={[
                { label:"P(beat hurdle)", value:pct(co.montecarlo.p_beat_hurdle,0) },
                { label:"P(loss)", value:pct(co.downside.p_loss,1) },
                { label:"5% VaR (MOIC)", value:mult(co.downside.var5_moic) },
                { label:"CVaR (MOIC)", value:mult(co.downside.cvar5_moic) },
              ]} />}
          </Section>

          <Section title="Sensitivity">
            <div className="grid gap-4 lg:grid-cols-2">
              {co.sensitivity && <SensitivityHeatmap grid={co.sensitivity.grid}
                iso={co.sensitivity.iso_frontier} hurdle={hurdle} />}
              {co.sobol && <SobolDrivers sobol={co.sobol} />}
            </div>
          </Section>

          <Section title="Operating model">
            {co.statements && <div className="space-y-4">
              <StatementTable title="Income statement" rows={co.statements.income} lines={IS_LINES} startYear={1} />
              <StatementTable title="Cash flow" rows={co.statements.cash_flow} lines={CF_LINES} startYear={1} />
              <StatementTable title="Balance sheet" rows={co.statements.balance_sheet} lines={BS_LINES} startYear={0} />
            </div>}
          </Section>

          <Section title="Debt">
            {co.debt_schedule && <DebtWaterfall schedule={co.debt_schedule} />}
            {co.debt_schedule && <DebtSchedule rows={co.debt_schedule} />}
            {co.solvers && <SolverCards solvers={co.solvers} />}
          </Section>
        </>
      )}

      <Section title="Take-private / deal">
        <div className="grid gap-4 lg:grid-cols-2">
          <DelistingCard d={co.delisting} />
          <FeasibilityBreakdown f={co.feasibility} />
        </div>
      </Section>
    </main>
  );
}
```

- [ ] **Step 2: Build** — Run (from `web-app/`): `npm run build`
Expected: static export succeeds; `/t/[ticker]` pre-renders for all passers incl. JUSTDIAL.

- [ ] **Step 3: Commit** `feat(web): assemble sectioned tear-sheet page`

---

### Task 11: Full green + visual verification

- [ ] **Step 1: Python + JS suites** — `python -m pytest -q` (repo root) and `npm run test` (web-app) → all PASS.
- [ ] **Step 2: Re-export + build** — `python tools/export_data.py --no-fetch`; then `cd web-app && npm run build` → succeeds.
- [ ] **Step 3: Visual (controller, via preview tools):** `npm run dev`; screenshot **a healthy tear sheet** (`/t/NATCOPHARM.NS`) — confirm all sections render (bridges, MC histogram + stat cards, heatmap with frontier overlay, 3 statement tables, debt waterfall + schedule, solvers, delisting, feasibility) in the Midnight theme; screenshot **the degenerate one** (`/t/JUSTDIAL.NS`) — confirm the n.m. notice + only the deal section. Fix any issues, re-verify.
- [ ] **Step 4: Commit** any visual fixes in their own commits.

---

## Done criteria for Phase 3

- `python -m pytest -q` green (incl. the 2 new grid tests); `npm run test` green (incl. new builders + StatementTable).
- `results.json` re-exported with `companies[t].sensitivity.grid` (5×5) for healthy names; degenerate names unchanged (`sensitivity: null`).
- `npm run build` static export succeeds; healthy tear sheet renders all sections; degenerate tear sheet shows the n.m. notice + deal section only.
- Only `src/analytics.py` changed in Python (one new function + the one-line `build_company_block` sensitivity wiring); no other `src/` math touched.

## Hand-off to Phase 4

Phase 4: repoint `vercel.json` to build/serve `web-app/` (replacing the old `web/`), add `.github/workflows/weekly.yml` (Monday cron → `python tools/export_data.py` → commit `results.json` → push → Vercel redeploys), and a README/run-docs pass. That flips the live site to the new app.
```
