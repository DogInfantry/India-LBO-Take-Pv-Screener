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
