import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { IrrBridge } from "@/lib/types";

export function buildIrrBridgeOption(b: IrrBridge): EChartsOption {
  const steps = [b.deleveraging, b.ebitda_growth, b.multiple_rerating];
  const cats = ["Deleveraging", "EBITDA growth", "Multiple re-rating", "Total IRR"];
  const base: number[] = []; const val: number[] = []; let run = 0;
  for (const s of steps) { base.push(Math.min(run, run + s)); val.push(Math.abs(s)); run += s; }
  base.push(0); val.push(b.total_irr);                       // final total from zero
  return {
    ...baseOption,
    tooltip: { ...baseOption.tooltip, trigger: "axis",
      formatter: (ps: any) =>
        `${ps[0].axisValue}: ${(((ps.find((p: any) => p.seriesName === "value")?.value) ?? 0) * 100).toFixed(1)}%` },
    xAxis: { type: "category", data: cats, axisLabel: { color: MIDNIGHT.muted, fontSize: 9, interval: 0 } },
    yAxis: { type: "value", axisLabel: { color: MIDNIGHT.axis, formatter: (v: number) => `${(v * 100) | 0}%` },
             splitLine: { lineStyle: { color: MIDNIGHT.edge } } },
    series: [
      { name: "base", type: "bar", stack: "t", itemStyle: { color: "transparent" }, data: base },
      { name: "value", type: "bar", stack: "t",
        itemStyle: { color: (p: any) => p.dataIndex === 3 ? MIDNIGHT.emerald : MIDNIGHT.emeraldDk,
                     borderRadius: [2, 2, 0, 0] }, data: val },
    ],
  };
}
