# Phase 2 — Dashboard (Next.js) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `web-app/` Next.js dashboard (`/`) — KPI band + dense-grid panels (IRR leaderboard, iso-IRR frontier, feasibility, Sobol drivers) in the Midnight-terminal theme — reading the Phase 1 `results.json` contract, plus a stub `/t/[ticker]` page so links resolve.

**Architecture:** Next.js App Router with `output: 'export'` (pure static → Vercel). `results.json` is read at build time by a typed server-side loader (`lib/data.ts`). Each chart is a pure ECharts **option-builder** function (Vitest-tested) wrapped by a thin `"use client"` `<EChart>` component that drives `echarts` core directly via a `useEffect` hook (no `echarts-for-react` — it relies on the removed `ReactDOM.render` and breaks under React 19). The page (server component) loads data once and passes typed slices down.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS v3, ECharts 5 (core, used directly), Vitest + @testing-library/react (jsdom).

---

## Reference: the contract this reads (verified against `web-app/public/data/results.json`)

```jsonc
{
  "as_of": "2026-06-17",
  "config": { "hurdle_irr": 0.2, "hold_years": 5, "control_premium_pct": 25.0 },
  "universe": { "screened": 46, "passed": 6 },
  "passers": [
    { "ticker": "NATCOPHARM.NS", "name": "NATCOPHARM", "irr": 0.156, "moic": 2.07,
      "degenerate": false, "feasibility": 96, "max_bid_premium_pct": null }
    // JUSTDIAL.NS has irr:null, moic:null, degenerate:true
  ],
  "companies": {
    "NATCOPHARM.NS": {
      "ticker","name",
      "returns": { "irr", "moic", "degenerate", "irr_bridge", "value_bridge" },
      "sensitivity": { "iso_frontier": { "target_irr": 0.2,
                       "points": [ { "exit_multiple": 8.7, "premium_pct": 4.85 }, ... ] } },
      "sobol": { "first_order": {revenue_growth,ebitda_shock,exit_multiple},
                 "total_order": {revenue_growth,ebitda_shock,exit_multiple} },
      "feasibility": { "score": 96, "components": {...}, "weights": {...} },
      // statements/debt_schedule/montecarlo/downside/solvers/delisting also present
      // (Phase 3 uses them). A degenerate company has those = null.
    }
  }
}
```

Phase 2 reads: `as_of`, `universe`, `config`, `passers[]`, and per top company
`sensitivity.iso_frontier` + `sobol.total_order`. **No 2D sensitivity grid exists
in the contract** — the heatmap is Phase 3; Phase 2 renders the iso-frontier.

## Midnight theme tokens (single source — used in tailwind.config + chart theme)

```
bg        #0b0f17   panel   #121826   border  #1e2738
text      #e6e9ef   muted   #8b95a6   faint   #5b6677
emerald   #34d399 (returns)   emeraldDk #059669
violet    #a78bfa (feasibility / sobol)
amber     #fbbf24   red #ef4444   redDk #b91c1c   (warm/risk end of scales)
font-sans: Inter (already used in repo)   font-mono: ui-monospace / JetBrains Mono (labels)
```

## File structure

```
web-app/
  package.json  next.config.mjs  tsconfig.json  postcss.config.mjs
  tailwind.config.ts  vitest.config.ts  vitest.setup.ts  .gitignore  README.md
  app/ layout.tsx  globals.css  page.tsx  t/[ticker]/page.tsx
  components/ EChart.tsx  KpiBand.tsx  IrrLeaderboard.tsx  IsoFrontier.tsx
              FeasibilityPanel.tsx  SobolDrivers.tsx
  lib/ types.ts  data.ts  theme.ts
       charts/ leaderboard.ts  frontier.ts  feasibility.ts  sobol.ts   (pure option-builders)
  public/data/results.json   (gitignored; produced by Phase 1 export_data.py)
```

Pure option-builders live in `lib/charts/` (Vitest-tested, no React). React chart
components in `components/` are thin `"use client"` wrappers: build option → `<EChart>`.

---

### Task 0: Scaffold the Next.js app

**Files:** create `web-app/package.json`, `next.config.mjs`, `tsconfig.json`, `postcss.config.mjs`, `tailwind.config.ts`, `app/globals.css`, `app/layout.tsx`, `app/page.tsx` (placeholder), `web-app/.gitignore`.

- [ ] **Step 1: Create `web-app/package.json`**

```json
{
  "name": "lbo-dashboard",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "15.1.6",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "echarts": "5.5.1"
  },
  "devDependencies": {
    "typescript": "5.7.3",
    "@types/node": "22.10.7",
    "@types/react": "19.0.7",
    "@types/react-dom": "19.0.3",
    "tailwindcss": "3.4.17",
    "postcss": "8.5.1",
    "autoprefixer": "10.4.20",
    "vitest": "2.1.8",
    "@vitejs/plugin-react": "4.3.4",
    "@testing-library/react": "16.1.0",
    "@testing-library/jest-dom": "6.6.3",
    "jsdom": "25.0.1"
  }
}
```

- [ ] **Step 2: Config files**

`web-app/next.config.mjs`:
```js
/** @type {import('next').NextConfig} */
const nextConfig = { output: 'export', images: { unoptimized: true } };
export default nextConfig;
```

`web-app/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022", "lib": ["dom","dom.iterable","esnext"], "allowJs": false,
    "skipLibCheck": true, "strict": true, "noEmit": true, "esModuleInterop": true,
    "module": "esnext", "moduleResolution": "bundler", "resolveJsonModule": true,
    "isolatedModules": true, "jsx": "preserve", "incremental": true,
    "plugins": [{ "name": "next" }], "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

`web-app/postcss.config.mjs`:
```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

`web-app/tailwind.config.ts`:
```ts
import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0f17", panel: "#121826", edge: "#1e2738",
        ink: "#e6e9ef", muted: "#8b95a6", faint: "#5b6677",
        emerald: { DEFAULT: "#34d399", dk: "#059669" },
        violet: "#a78bfa", amber: "#fbbf24", danger: "#ef4444",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["ui-monospace", "JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
```

`web-app/.gitignore`:
```
node_modules/
.next/
out/
public/data/results.json
*.tsbuildinfo
next-env.d.ts
```

- [ ] **Step 3: Minimal app shell**

`web-app/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
body { @apply bg-bg text-ink font-sans; }
```

`web-app/app/layout.tsx`:
```tsx
import "./globals.css";
export const metadata = { title: "India LBO Take-Private Screener" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><body className="min-h-screen antialiased">{children}</body></html>
  );
}
```

`web-app/app/page.tsx` (placeholder, replaced in Task 8):
```tsx
export default function Page() { return <main className="p-8">Dashboard</main>; }
```

- [ ] **Step 4: Install + verify the empty app builds (static export)**

Run (from `web-app/`): `npm install` then `npm run build`
Expected: build succeeds, produces `web-app/out/` with static HTML. If `npm install` is slow, that's fine.

- [ ] **Step 5: Commit**

```bash
git add web-app/ ':!web-app/node_modules' ':!web-app/out' ':!web-app/.next'
git commit -m "feat(web): scaffold Next.js static-export app with Midnight Tailwind theme"
```

---

### Task 1: Contract types + typed loader (`lib/types.ts`, `lib/data.ts`)

**Files:** create `web-app/lib/types.ts`, `web-app/lib/data.ts`, `web-app/vitest.config.ts`, `web-app/vitest.setup.ts`, test `web-app/lib/data.test.ts`.

- [ ] **Step 1: Vitest config**

`web-app/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";
export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", setupFiles: ["./vitest.setup.ts"], globals: true },
  resolve: { alias: { "@": path.resolve(__dirname) } },
});
```

`web-app/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 2: Write the failing test** (`web-app/lib/data.test.ts`)

```ts
import { describe, it, expect } from "vitest";
import { loadResults, topReturns } from "@/lib/data";

describe("loadResults", () => {
  const r = loadResults();
  it("parses the real contract", () => {
    expect(r.as_of).toBeTruthy();
    expect(r.passers.length).toBeGreaterThan(0);
  });
  it("every passer has a matching company block", () => {
    for (const p of r.passers) expect(r.companies[p.ticker]).toBeDefined();
  });
  it("top IRR/MOIC exclude degenerate names", () => {
    const t = topReturns(r.passers);
    const degens = r.passers.filter((p) => p.degenerate).map((p) => p.ticker);
    expect(degens.length).toBeGreaterThan(0);          // JUSTDIAL is degenerate
    expect(t.topIrr).not.toBeNull();
    // the degenerate names never set the max
    expect(t.topIrrTicker && degens.includes(t.topIrrTicker)).toBeFalsy();
  });
});
```

- [ ] **Step 3: Run — expect FAIL** (module missing).
Run (from `web-app/`): `npm run test`

- [ ] **Step 4: Implement types + loader**

`web-app/lib/types.ts`:
```ts
export interface IsoFrontierPoint { exit_multiple: number; premium_pct: number; }
export interface Passer {
  ticker: string; name: string;
  irr: number | null; moic: number | null;
  degenerate: boolean; feasibility: number;
  max_bid_premium_pct: number | null;
}
export interface CompanyBlock {
  ticker: string; name: string;
  returns: { irr: number | null; moic: number | null; degenerate: boolean;
             irr_bridge: unknown | null; value_bridge: unknown | null };
  sensitivity: { iso_frontier: { target_irr: number; points: IsoFrontierPoint[] } } | null;
  sobol: { first_order: Record<string, number>;
           total_order: Record<string, number> } | null;
  feasibility: { score: number; components: Record<string, number>;
                 weights: Record<string, number> };
  // statements/debt_schedule/montecarlo/downside/solvers/delisting: Phase 3
  [k: string]: unknown;
}
export interface Results {
  as_of: string;
  config: { hurdle_irr: number; hold_years: number; control_premium_pct: number };
  universe: { screened: number; passed: number };
  passers: Passer[];
  companies: Record<string, CompanyBlock>;
}
```

`web-app/lib/data.ts`:
```ts
import fs from "node:fs";
import path from "node:path";
import type { Results, Passer } from "./types";

const CONTRACT = path.join(process.cwd(), "public", "data", "results.json");

export function loadResults(): Results {
  if (!fs.existsSync(CONTRACT)) {
    throw new Error(
      `Missing ${CONTRACT}. Run: python tools/export_data.py --no-fetch (from repo root) first.`
    );
  }
  const raw = JSON.parse(fs.readFileSync(CONTRACT, "utf-8")) as Results;
  if (!raw.passers || !raw.companies) throw new Error("results.json is malformed");
  return raw;
}

export function topReturns(passers: Passer[]) {
  const live = passers.filter((p) => !p.degenerate && p.irr != null && p.moic != null);
  const byIrr = [...live].sort((a, b) => (b.irr! - a.irr!));
  const byMoic = [...live].sort((a, b) => (b.moic! - a.moic!));
  return {
    topIrr: byIrr[0]?.irr ?? null, topIrrTicker: byIrr[0]?.ticker ?? null,
    topMoic: byMoic[0]?.moic ?? null,
    topFeasibility: Math.max(...passers.map((p) => p.feasibility)),
  };
}
```

- [ ] **Step 5: Run — expect PASS.** Then **commit**:
```bash
git add web-app/lib web-app/vitest.config.ts web-app/vitest.setup.ts
git commit -m "feat(web): typed results.json loader + contract types (degenerate-aware)"
```

---

### Task 2: Chart theme + `EChart` wrapper

**Files:** create `web-app/lib/theme.ts`, `web-app/components/EChart.tsx`, test `web-app/lib/theme.test.ts`.

- [ ] **Step 1: Failing test** (`web-app/lib/theme.test.ts`)

```ts
import { describe, it, expect } from "vitest";
import { MIDNIGHT } from "@/lib/theme";
it("exposes the midnight palette", () => {
  expect(MIDNIGHT.emerald).toBe("#34d399");
  expect(MIDNIGHT.bg).toBe("#0b0f17");
  expect(MIDNIGHT.axis).toBeTruthy();
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`web-app/lib/theme.ts`:
```ts
export const MIDNIGHT = {
  bg: "#0b0f17", panel: "#121826", edge: "#1e2738",
  ink: "#e6e9ef", muted: "#8b95a6", axis: "#5b6677",
  emerald: "#34d399", emeraldDk: "#059669", violet: "#a78bfa",
  amber: "#fbbf24", danger: "#ef4444",
  // diverging green->amber->red scale for value/risk encodings
  scale: ["#065f46", "#059669", "#34d399", "#fbbf24", "#ef4444"],
};
// Base ECharts option fragment every chart spreads in for consistent styling.
export const baseOption = {
  backgroundColor: "transparent",
  textStyle: { color: MIDNIGHT.muted, fontFamily: "ui-monospace, monospace" },
  grid: { left: 8, right: 12, top: 16, bottom: 8, containLabel: true },
  tooltip: { trigger: "item", backgroundColor: MIDNIGHT.panel,
             borderColor: MIDNIGHT.edge, textStyle: { color: MIDNIGHT.ink } },
};
```

`web-app/components/EChart.tsx` (drives echarts core directly — React-19-safe, no echarts-for-react):
```tsx
"use client";
import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

export function EChart({ option, height = 200 }: { option: EChartsOption; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" }); // crisp, export-safe
    chart.setOption(option);
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); chart.dispose(); };
  }, [option]);
  return <div ref={ref} style={{ height, width: "100%" }} />;
}
```

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): Midnight chart theme + EChart wrapper`

---

### Task 3: IRR leaderboard (`lib/charts/leaderboard.ts` + component)

**Files:** create `web-app/lib/charts/leaderboard.ts`, `web-app/components/IrrLeaderboard.tsx`, test `web-app/lib/charts/leaderboard.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect } from "vitest";
import { buildLeaderboardOption } from "@/lib/charts/leaderboard";
import type { Passer } from "@/lib/types";

const passers: Passer[] = [
  { ticker: "A.NS", name: "A", irr: 0.15, moic: 2, degenerate: false, feasibility: 90, max_bid_premium_pct: null },
  { ticker: "B.NS", name: "B", irr: 0.09, moic: 1.5, degenerate: false, feasibility: 80, max_bid_premium_pct: null },
  { ticker: "JD.NS", name: "JD", irr: null, moic: null, degenerate: true, feasibility: 70, max_bid_premium_pct: null },
];

it("ranks live names by IRR descending and excludes degenerate from the bars", () => {
  const o: any = buildLeaderboardOption(passers, 0.20);
  const cats = o.yAxis.data;                       // category labels
  expect(cats).toEqual(["B", "A"]);                // ECharts bars: bottom->top, so asc
  const vals = o.series[0].data.map((d: any) => d.value);
  expect(Math.max(...vals)).toBeCloseTo(0.15);
  expect(vals).not.toContain(null);                // JD excluded
});
it("includes a markLine at the hurdle", () => {
  const o: any = buildLeaderboardOption(passers, 0.20);
  expect(JSON.stringify(o.series[0].markLine)).toContain("0.2");
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`web-app/lib/charts/leaderboard.ts`:
```ts
import type { EChartsOption } from "echarts";
import type { Passer } from "@/lib/types";
import { MIDNIGHT, baseOption } from "@/lib/theme";

export function buildLeaderboardOption(passers: Passer[], hurdle: number): EChartsOption {
  const live = passers.filter((p) => !p.degenerate && p.irr != null)
                      .sort((a, b) => a.irr! - b.irr!);   // asc -> top bar is highest
  return {
    ...baseOption,
    tooltip: { ...baseOption.tooltip, trigger: "axis",
               valueFormatter: (v: any) => `${(v * 100).toFixed(1)}%` },
    xAxis: { type: "value", axisLabel: { formatter: (v: number) => `${(v*100)|0}%`,
             color: MIDNIGHT.axis }, splitLine: { lineStyle: { color: MIDNIGHT.edge } } },
    yAxis: { type: "category", data: live.map((p) => p.name),
             axisLabel: { color: MIDNIGHT.muted } },
    series: [{
      type: "bar", barWidth: 14,
      // object form ({value}) so tests can read d.value; color is series-level
      data: live.map((p) => ({ value: p.irr })),
      itemStyle: { color: MIDNIGHT.emerald, borderRadius: [0, 3, 3, 0] },
      markLine: { silent: true, symbol: "none",
        lineStyle: { color: MIDNIGHT.danger, type: "dashed" },
        data: [{ xAxis: hurdle }], label: { formatter: "hurdle", color: MIDNIGHT.danger } },
    }],
  };
}
```
> Note: `data` is in object form `{ value: p.irr }` (not bare numbers) so the
> Step-1 test's `data.map(d => d.value)` works; bar color is set once at the
> series level, not per datum.

`web-app/components/IrrLeaderboard.tsx`:
```tsx
"use client";
import Link from "next/link";
import type { Passer } from "@/lib/types";
import { buildLeaderboardOption } from "@/lib/charts/leaderboard";
import { EChart } from "./EChart";

export function IrrLeaderboard({ passers, hurdle }: { passers: Passer[]; hurdle: number }) {
  const degen = passers.filter((p) => p.degenerate);
  return (
    <div>
      <EChart option={buildLeaderboardOption(passers, hurdle)}
              height={Math.max(160, 34 * passers.filter((p) => !p.degenerate).length)} />
      <ul className="mt-2 space-y-1 text-xs">
        {passers.map((p) => (
          <li key={p.ticker}>
            <Link href={`/t/${p.ticker}`}
              className={p.degenerate ? "text-faint italic" : "text-muted hover:text-ink"}>
              {p.name}{p.degenerate ? " — n.m. (net cash > mkt cap)" : ""}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): IRR leaderboard panel`

---

### Task 4: Iso-IRR frontier (`lib/charts/frontier.ts` + component)

**Files:** create `web-app/lib/charts/frontier.ts`, `web-app/components/IsoFrontier.tsx`, test `web-app/lib/charts/frontier.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { it, expect } from "vitest";
import { buildFrontierOption } from "@/lib/charts/frontier";

const iso = { target_irr: 0.2, points: [
  { exit_multiple: 8.7, premium_pct: 4.85 }, { exit_multiple: 10.7, premium_pct: 18.02 } ] };

it("maps frontier points to an [exit_multiple, premium] line series", () => {
  const o: any = buildFrontierOption(iso);
  expect(o.series[0].type).toBe("line");
  expect(o.series[0].data).toEqual([[8.7, 4.85], [10.7, 18.02]]);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`web-app/lib/charts/frontier.ts`:
```ts
import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { IsoFrontierPoint } from "@/lib/types";

export function buildFrontierOption(
  iso: { target_irr: number; points: IsoFrontierPoint[] }
): EChartsOption {
  const data = iso.points.map((p) => [p.exit_multiple, p.premium_pct]);
  return {
    ...baseOption,
    tooltip: { ...baseOption.tooltip, trigger: "axis",
      formatter: (ps: any) => `exit ${ps[0].value[0]}x → ${ps[0].value[1].toFixed(1)}% premium` },
    xAxis: { type: "value", name: "exit multiple", nameTextStyle: { color: MIDNIGHT.axis },
             axisLabel: { color: MIDNIGHT.axis }, splitLine: { lineStyle: { color: MIDNIGHT.edge } } },
    yAxis: { type: "value", name: "break-even premium %", nameTextStyle: { color: MIDNIGHT.axis },
             axisLabel: { color: MIDNIGHT.axis }, splitLine: { lineStyle: { color: MIDNIGHT.edge } } },
    series: [{
      type: "line", smooth: true, data,
      lineStyle: { color: MIDNIGHT.amber, width: 2 },
      areaStyle: { color: "rgba(251,191,36,0.10)" },
      symbol: "circle", symbolSize: 6, itemStyle: { color: MIDNIGHT.amber },
    }],
  };
}
```

`web-app/components/IsoFrontier.tsx`:
```tsx
"use client";
import { buildFrontierOption } from "@/lib/charts/frontier";
import { EChart } from "./EChart";
import type { IsoFrontierPoint } from "@/lib/types";

export function IsoFrontier({ iso }: { iso: { target_irr: number; points: IsoFrontierPoint[] } }) {
  return <EChart option={buildFrontierOption(iso)} height={200} />;
}
```

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): iso-IRR frontier panel`

---

### Task 5: Feasibility panel (`lib/charts/feasibility.ts` + component)

**Files:** create `web-app/lib/charts/feasibility.ts`, `web-app/components/FeasibilityPanel.tsx`, test `web-app/lib/charts/feasibility.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { it, expect } from "vitest";
import { buildFeasibilityOption } from "@/lib/charts/feasibility";
import type { Passer } from "@/lib/types";
const ps: Passer[] = [
  { ticker:"A.NS",name:"A",irr:.1,moic:1.5,degenerate:false,feasibility:96,max_bid_premium_pct:null },
  { ticker:"B.NS",name:"B",irr:.1,moic:1.5,degenerate:false,feasibility:87,max_bid_premium_pct:null },
];
it("ranks feasibility descending (top bar highest)", () => {
  const o: any = buildFeasibilityOption(ps);
  expect(o.yAxis.data).toEqual(["B", "A"]);        // asc so A on top
  expect(Math.max(...o.series[0].data)).toBe(96);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`web-app/lib/charts/feasibility.ts`:
```ts
import type { EChartsOption } from "echarts";
import type { Passer } from "@/lib/types";
import { MIDNIGHT, baseOption } from "@/lib/theme";

export function buildFeasibilityOption(passers: Passer[]): EChartsOption {
  const ranked = [...passers].sort((a, b) => a.feasibility - b.feasibility);
  return {
    ...baseOption,
    xAxis: { type: "value", max: 100, axisLabel: { color: MIDNIGHT.axis },
             splitLine: { lineStyle: { color: MIDNIGHT.edge } } },
    yAxis: { type: "category", data: ranked.map((p) => p.name),
             axisLabel: { color: MIDNIGHT.muted } },
    series: [{ type: "bar", barWidth: 14, data: ranked.map((p) => p.feasibility),
               itemStyle: { color: MIDNIGHT.violet, borderRadius: [0, 3, 3, 0] } }],
  };
}
```

`web-app/components/FeasibilityPanel.tsx`:
```tsx
"use client";
import type { Passer } from "@/lib/types";
import { buildFeasibilityOption } from "@/lib/charts/feasibility";
import { EChart } from "./EChart";
export function FeasibilityPanel({ passers }: { passers: Passer[] }) {
  return <EChart option={buildFeasibilityOption(passers)} height={Math.max(160, 30 * passers.length)} />;
}
```

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): feasibility panel`

---

### Task 6: Sobol drivers (`lib/charts/sobol.ts` + component)

**Files:** create `web-app/lib/charts/sobol.ts`, `web-app/components/SobolDrivers.tsx`, test `web-app/lib/charts/sobol.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { it, expect } from "vitest";
import { buildSobolOption } from "@/lib/charts/sobol";
const sobol = { first_order: {}, total_order: { revenue_growth: 0.41, exit_multiple: 0.39, ebitda_shock: 0.20 } };
it("ranks drivers by total-order variance share, descending top bar", () => {
  const o: any = buildSobolOption(sobol);
  expect(o.yAxis.data[o.yAxis.data.length - 1]).toBe("revenue_growth"); // top = highest
  expect(Math.max(...o.series[0].data)).toBeCloseTo(0.41);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`web-app/lib/charts/sobol.ts`:
```ts
import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";

export function buildSobolOption(
  sobol: { total_order: Record<string, number> }
): EChartsOption {
  const entries = Object.entries(sobol.total_order).sort((a, b) => a[1] - b[1]); // asc
  return {
    ...baseOption,
    tooltip: { ...baseOption.tooltip, trigger: "axis",
               valueFormatter: (v: any) => v.toFixed(2) },
    xAxis: { type: "value", axisLabel: { color: MIDNIGHT.axis },
             splitLine: { lineStyle: { color: MIDNIGHT.edge } } },
    yAxis: { type: "category", data: entries.map((e) => e[0]),
             axisLabel: { color: MIDNIGHT.muted } },
    series: [{ type: "bar", barWidth: 14, data: entries.map((e) => e[1]),
               itemStyle: { color: MIDNIGHT.violet, borderRadius: [0, 3, 3, 0] } }],
  };
}
```

`web-app/components/SobolDrivers.tsx`:
```tsx
"use client";
import { buildSobolOption } from "@/lib/charts/sobol";
import { EChart } from "./EChart";
export function SobolDrivers({ sobol }: { sobol: { total_order: Record<string, number> } }) {
  return <EChart option={buildSobolOption(sobol)} height={160} />;
}
```

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): Sobol drivers panel`

---

### Task 7: KPI band (`components/KpiBand.tsx`)

**Files:** create `web-app/lib/kpis.ts`, `web-app/components/KpiBand.tsx`, test `web-app/lib/kpis.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { it, expect } from "vitest";
import { kpis } from "@/lib/kpis";
import { loadResults } from "@/lib/data";
it("builds KPI tiles from the real contract, top excludes degenerate", () => {
  const k = kpis(loadResults());
  expect(k.find((t) => t.label === "Passers")?.value).toMatch(/\d/);
  const topIrr = k.find((t) => t.label === "Top IRR")!;
  expect(topIrr.value).toMatch(/%$/);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`web-app/lib/kpis.ts`:
```ts
import type { Results } from "./types";
import { topReturns } from "./data";

export function kpis(r: Results) {
  const t = topReturns(r.passers);
  const pct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
  return [
    { label: "Passers", value: String(r.universe.passed) },
    { label: "Screened", value: String(r.universe.screened) },
    { label: "Top IRR", value: pct(t.topIrr), accent: "emerald" },
    { label: "Top MOIC", value: t.topMoic == null ? "—" : `${t.topMoic.toFixed(2)}x`, accent: "emerald" },
    { label: "Top feasibility", value: String(t.topFeasibility), accent: "violet" },
  ];
}
```

`web-app/components/KpiBand.tsx`:
```tsx
import type { Results } from "@/lib/types";
import { kpis } from "@/lib/kpis";

export function KpiBand({ results }: { results: Results }) {
  const tiles = kpis(results);
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-md border border-edge bg-panel px-3 py-2">
          <div className={`font-mono text-lg leading-tight ${
            t.accent === "violet" ? "text-violet" : t.accent === "emerald" ? "text-emerald" : "text-ink"}`}>
            {t.value}
          </div>
          <div className="text-[10px] uppercase tracking-wide text-faint">{t.label}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run — expect PASS.** **Commit:** `feat(web): KPI band`

---

### Task 8: Assemble the dashboard page (`app/page.tsx`)

**Files:** modify `web-app/app/page.tsx`.

- [ ] **Step 1: Implement the dense-grid dashboard** (server component loads data, passes typed slices down)

```tsx
import { loadResults } from "@/lib/data";
import { KpiBand } from "@/components/KpiBand";
import { IrrLeaderboard } from "@/components/IrrLeaderboard";
import { IsoFrontier } from "@/components/IsoFrontier";
import { FeasibilityPanel } from "@/components/FeasibilityPanel";
import { SobolDrivers } from "@/components/SobolDrivers";

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-edge bg-panel p-3">
      <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wider text-faint">{title}</h2>
      {children}
    </section>
  );
}

export default function Page() {
  const r = loadResults();
  // highest-IRR live name drives the single-company panels (order-independent)
  const top = [...r.passers].filter((p) => !p.degenerate && p.irr != null)
                .sort((a, b) => b.irr! - a.irr!)[0] ?? r.passers[0];
  const topCo = r.companies[top.ticker];
  return (
    <main className="mx-auto max-w-6xl p-6">
      <header className="mb-4">
        <h1 className="font-mono text-sm tracking-[0.2em] text-faint">
          INDIA LBO TAKE-PRIVATE SCREENER · AS OF {r.as_of.toUpperCase()}
        </h1>
      </header>
      <KpiBand results={r} />
      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel title="Base-case IRR — ranked"><IrrLeaderboard passers={r.passers} hurdle={r.config.hurdle_irr} /></Panel>
        <Panel title={`Iso-IRR frontier · ${top.name}`}>
          {topCo.sensitivity ? <IsoFrontier iso={topCo.sensitivity.iso_frontier} /> : null}
        </Panel>
        <Panel title="Take-private feasibility"><FeasibilityPanel passers={r.passers} /></Panel>
        <Panel title={`IRR variance drivers (Sobol) · ${top.name}`}>
          {topCo.sobol ? <SobolDrivers sobol={topCo.sobol} /> : null}
        </Panel>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Build the static export**
Run (from `web-app/`): `npm run build`
Expected: build succeeds; `out/index.html` generated.

- [ ] **Step 3: Commit** `feat(web): assemble dense-grid dashboard page`

---

### Task 9: Stub tear sheet `/t/[ticker]`

**Files:** create `web-app/app/t/[ticker]/page.tsx`.

- [ ] **Step 1: Implement stub with static params**

```tsx
import { loadResults } from "@/lib/data";

export function generateStaticParams() {
  return loadResults().passers.map((p) => ({ ticker: p.ticker }));
}

export default async function TearSheet({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const r = loadResults();
  const co = r.companies[ticker];
  if (!co) return <main className="p-6">Unknown ticker.</main>;
  const pct = (v: number | null) => (v == null ? "n.m." : `${(v * 100).toFixed(1)}%`);
  return (
    <main className="mx-auto max-w-4xl p-6">
      <a href="/" className="font-mono text-xs text-faint hover:text-ink">← dashboard</a>
      <h1 className="mt-2 text-2xl font-semibold">{co.name}</h1>
      <p className="mt-1 font-mono text-sm text-muted">
        IRR {pct(co.returns.irr)} · MOIC {co.returns.moic == null ? "n.m." : co.returns.moic.toFixed(2) + "x"}
        · feasibility {co.feasibility.score}
      </p>
      <p className="mt-6 text-sm text-faint">Full tear sheet — Phase 3.</p>
    </main>
  );
}
```

- [ ] **Step 2: Build**
Run (from `web-app/`): `npm run build`
Expected: static export emits `out/t/<ticker>/index.html` for each passer (incl. JUSTDIAL).

- [ ] **Step 3: Commit** `feat(web): stub tear-sheet route with static params`

---

### Task 10: Full green + visual verification

**Files:** none (verification); maybe `web-app/README.md`.

- [ ] **Step 1: Full Vitest suite** — Run (from `web-app/`): `npm run test` → all PASS.
- [ ] **Step 2: Static export** — Run: `npm run build` → succeeds, `out/` populated.
- [ ] **Step 3: Visual check (controller does this via preview tools):** start the dev server (`npm run dev` in `web-app/`), open the preview, screenshot the dashboard, confirm KPI band + 4 panels render with real data in the Midnight theme, and that JUSTDIAL shows dimmed "n.m." Fix any visual issues, re-verify.
- [ ] **Step 4: README** — add `web-app/README.md`: prerequisite `python tools/export_data.py --no-fetch` (writes the gitignored contract), then `npm install && npm run dev` / `npm run build`.
- [ ] **Step 5: Commit** `docs(web): dashboard run instructions` (+ any visual fixes in their own commits).

---

## Done criteria for Phase 2

- `web-app/` builds a static export (`npm run build` → `out/`) with no runtime data fetch.
- `npm run test` green (loader, KPIs, and every chart option-builder unit-tested, degenerate-aware).
- Dashboard renders KPI band + leaderboard/iso-frontier/feasibility/Sobol in the Midnight theme; JUSTDIAL dimmed to "n.m."; leaderboard rows link to a working stub tear sheet.
- No Python (`src/`, `tools/`) modified.
- `vercel.json` is NOT yet repointed (still serves the old `web/`) — that's Phase 4.

## Hand-off to Phase 3

Phase 3 fills `/t/[ticker]` (3-statements, debt waterfall, IRR & value bridges, Monte Carlo fan, downside/CVaR, solver panels, delisting) and adds the **2D premium×exit sensitivity heatmap** — which requires wiring `sensitivity_grid_premium` into `build_company_block` (a Phase 1-contract addition) so `companies[t].sensitivity` carries a `grid` alongside `iso_frontier`.
