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
