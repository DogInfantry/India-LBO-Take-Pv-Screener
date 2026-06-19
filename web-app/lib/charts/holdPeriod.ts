import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";

export interface HoldRow { year: number; irr: number | null; }
export interface CompanySeries { name: string; ticker: string; data: HoldRow[]; }

// Five distinct colors — one per company slot
const LINE_COLORS = [
  MIDNIGHT.emerald, MIDNIGHT.violet, MIDNIGHT.amber,
  "#60a5fa", // blue-400
  "#f472b6", // pink-400
];

export function buildHoldPeriodOption(
  series: CompanySeries[],
  hurdle: number
): EChartsOption {
  return {
    ...baseOption,
    grid: { ...baseOption.grid, top: 36 },
    legend: {
      top: 4, textStyle: { color: MIDNIGHT.muted, fontSize: 10 },
      itemWidth: 12, itemHeight: 2,
    },
    xAxis: {
      type: "category",
      data: [1, 2, 3, 4, 5].map(String),
      name: "Hold year", nameLocation: "middle", nameGap: 22,
      nameTextStyle: { color: MIDNIGHT.muted, fontSize: 9 },
      axisLabel: { color: MIDNIGHT.axis },
      axisLine: { lineStyle: { color: MIDNIGHT.edge } },
    },
    yAxis: {
      type: "value", name: "IRR", nameLocation: "middle", nameGap: 36,
      nameTextStyle: { color: MIDNIGHT.muted, fontSize: 9 },
      axisLabel: { color: MIDNIGHT.axis, formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
      splitLine: { lineStyle: { color: MIDNIGHT.edge } },
    },
    series: [
      // hurdle line first so it renders behind
      {
        name: "20% hurdle", type: "line", data: Array(5).fill(hurdle),
        lineStyle: { type: "dashed", color: MIDNIGHT.muted, width: 1 },
        symbol: "none", itemStyle: { color: MIDNIGHT.muted },
      },
      ...series.map((s, i) => ({
        name: s.name,
        type: "line" as const,
        data: s.data.map((r) => r.irr ?? null),
        smooth: true,
        symbol: "circle", symbolSize: 5,
        itemStyle: { color: LINE_COLORS[i % LINE_COLORS.length] },
        lineStyle: { color: LINE_COLORS[i % LINE_COLORS.length], width: 2 },
        tooltip: { valueFormatter: (v: any) => v != null ? `${(v * 100).toFixed(1)}%` : "—" },
      })),
    ],
    tooltip: {
      ...baseOption.tooltip, trigger: "axis",
      formatter: (ps: any) => {
        const year = ps[0]?.axisValue;
        return ps.map((p: any) =>
          p.seriesName === "20% hurdle" ? "" :
          `${p.marker}${p.seriesName}: ${p.value != null ? (p.value * 100).toFixed(1) + "%" : "—"}`
        ).filter(Boolean).join("<br/>") || `Year ${year}`;
      },
    },
  };
}
