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
