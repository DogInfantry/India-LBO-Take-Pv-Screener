import { it, expect } from "vitest";
import { buildHeatmapOption } from "@/lib/charts/heatmap";
const grid = { premiums_pct: [0, 10, 20], exit_multiples: [6, 7, 8],
  irr: [[0.30, 0.34, 0.38], [0.22, 0.26, 0.30], [0.14, 0.18, 0.22]] };
const iso = { target_irr: 0.2, points: [{ exit_multiple: 7, premium_pct: 14 }, { exit_multiple: 8, premium_pct: 21 }] };
it("emits one heatmap cell per grid entry + a visualMap + a frontier line series", () => {
  const o: any = buildHeatmapOption(grid, iso, 0.20);
  expect(o.series[0].type).toBe("heatmap");
  expect(o.series[0].data.length).toBe(9);              // 3x3
  expect(o.visualMap).toBeTruthy();
  expect(o.series.some((s: any) => s.type === "line")).toBe(true);   // frontier overlay
});
