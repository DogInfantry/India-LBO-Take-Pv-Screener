import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { ValueBridge } from "@/lib/types";

export function buildValueBridgeOption(b: ValueBridge): EChartsOption {
  const deltas = [
    ["EBITDA growth", b.ebitda_growth], ["Multiple", b.multiple_change],
    ["Debt paydown", b.debt_paydown], ["Fees/other", b.fees_and_other],
  ] as [string, number][];
  const cats = ["Entry equity", ...deltas.map((d) => d[0]), "Exit equity"];
  const base: number[] = [0]; const val: number[] = [b.entry_equity]; let run = b.entry_equity;
  for (const [, d] of deltas) { base.push(Math.min(run, run + d)); val.push(Math.abs(d)); run += d; }
  base.push(0); val.push(b.exit_equity);
  return {
    ...baseOption,
    tooltip: { ...baseOption.tooltip, trigger: "axis" },
    xAxis: { type: "category", data: cats,
             axisLabel: { color: MIDNIGHT.muted, fontSize: 9, interval: 0, rotate: 20 } },
    yAxis: { type: "value", axisLabel: { color: MIDNIGHT.axis }, splitLine: { lineStyle: { color: MIDNIGHT.edge } } },
    series: [
      { name: "base", type: "bar", stack: "v", itemStyle: { color: "transparent" }, data: base },
      { name: "value", type: "bar", stack: "v", data: val,
        itemStyle: { color: (p: any) => (p.dataIndex === 0 || p.dataIndex === cats.length - 1)
          ? MIDNIGHT.emerald : (deltas[p.dataIndex - 1]?.[1] ?? 0) >= 0 ? MIDNIGHT.emeraldDk : MIDNIGHT.danger,
          borderRadius: [2, 2, 0, 0] } },
    ],
  };
}
