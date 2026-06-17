import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { SensitivityGrid, IsoFrontierPoint } from "@/lib/types";

export function buildHeatmapOption(
  grid: SensitivityGrid, iso: { target_irr: number; points: IsoFrontierPoint[] }, hurdle: number
): EChartsOption {
  void hurdle;
  const cells: [number, number, number][] = [];
  let min = Infinity, max = -Infinity;
  grid.irr.forEach((row, r) => row.forEach((v, c) => {
    if (v != null) { cells.push([c, r, v]); min = Math.min(min, v); max = Math.max(max, v); }
  }));
  // frontier points -> [exitIndex(nearest), premiumIndex(interpolated)] in grid coords
  const xi = (xm: number) => grid.exit_multiples.reduce(
    (best, e, i) => Math.abs(e - xm) < Math.abs(grid.exit_multiples[best] - xm) ? i : best, 0);
  const yi = (pp: number) => {
    const idx = grid.premiums_pct.findIndex((p) => p >= pp);
    return idx <= 0 ? 0 : idx - 1 + (pp - grid.premiums_pct[idx - 1]) /
      (grid.premiums_pct[idx] - grid.premiums_pct[idx - 1]);
  };
  const frontier = iso.points.map((p) => [xi(p.exit_multiple), yi(p.premium_pct)]);
  return {
    ...baseOption,
    tooltip: { position: "top", backgroundColor: MIDNIGHT.panel, borderColor: MIDNIGHT.edge,
      textStyle: { color: MIDNIGHT.ink },
      formatter: (p: any) =>
        `prem ${grid.premiums_pct[p.value[1]]}% · exit ${grid.exit_multiples[p.value[0]]}x → IRR ${(p.value[2] * 100).toFixed(1)}%` },
    grid: { left: 48, right: 16, top: 12, bottom: 36 },
    xAxis: { type: "category", data: grid.exit_multiples.map(String), name: "exit ×",
             axisLabel: { color: MIDNIGHT.axis }, splitArea: { show: true } },
    yAxis: { type: "category", data: grid.premiums_pct.map((p) => `${p}%`), name: "premium",
             axisLabel: { color: MIDNIGHT.axis }, splitArea: { show: true } },
    visualMap: { type: "continuous" as const, min, max, calculable: false, orient: "horizontal" as const,
      left: "center", bottom: 0,
      inRange: { color: ["#b91c1c", "#ef4444", "#fbbf24", "#34d399", "#059669"] },
      textStyle: { color: MIDNIGHT.axis }, formatter: (v: any) => `${(Number(v) * 100) | 0}%` },
    series: [
      { type: "heatmap", data: cells,
        label: { show: true, color: "#0b0f17", fontSize: 9, formatter: (p: any) => `${(p.value[2] * 100).toFixed(0)}` } },
      { type: "line", data: frontier, smooth: true, symbol: "none",
        lineStyle: { color: MIDNIGHT.ink, width: 2, type: "dashed" }, tooltip: { show: false }, z: 5 },
    ],
  };
}
