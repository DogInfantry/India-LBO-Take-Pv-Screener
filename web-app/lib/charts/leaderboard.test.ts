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
