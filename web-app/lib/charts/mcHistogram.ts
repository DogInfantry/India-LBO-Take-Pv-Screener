import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";

export function buildMcHistogramOption(samples: number[], hurdle: number, bins = 30): EChartsOption {
  const lo = Math.min(...samples), hi = Math.max(...samples);
  const w = (hi - lo) / bins || 1;
  const counts = new Array(bins).fill(0);
  for (const s of samples) counts[Math.min(bins - 1, Math.max(0, Math.floor((s - lo) / w)))]++;
  const data = counts.map((c, i) => ({ value: c,
    itemStyle: { color: (lo + (i + 0.5) * w) >= hurdle ? MIDNIGHT.emerald : MIDNIGHT.axis } }));
  return {
    ...baseOption,
    tooltip: { ...baseOption.tooltip, trigger: "axis" },
    xAxis: { type: "category", data: counts.map((_, i) => `${((lo + i * w) * 100).toFixed(0)}%`),
             axisLabel: { color: MIDNIGHT.axis, interval: Math.floor(bins / 6) } },
    yAxis: { type: "value", axisLabel: { color: MIDNIGHT.axis }, splitLine: { lineStyle: { color: MIDNIGHT.edge } } },
    series: [{ type: "bar", data, barWidth: "96%",
      markLine: { silent: true, symbol: "none", lineStyle: { color: MIDNIGHT.danger, type: "dashed" },
        data: [{ xAxis: Math.round((hurdle - lo) / w) }],
        label: { formatter: `hurdle ${(hurdle * 100) | 0}%`, color: MIDNIGHT.danger } } }],
  };
}
