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
