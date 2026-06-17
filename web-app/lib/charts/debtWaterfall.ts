import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { DebtScheduleRow } from "@/lib/types";

export function buildDebtWaterfallOption(sched: DebtScheduleRow[]): EChartsOption {
  const years = sched.map((r) => `Y${r.year}`);
  const mk = (name: string, key: keyof DebtScheduleRow, color: string) =>
    ({ name, type: "bar", stack: "d", data: sched.map((r) => r[key] as number), itemStyle: { color } });
  return {
    ...baseOption,
    legend: { textStyle: { color: MIDNIGHT.muted }, top: 0, right: 0 },
    tooltip: { ...baseOption.tooltip, trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "category", data: years, axisLabel: { color: MIDNIGHT.axis } },
    yAxis: { type: "value", axisLabel: { color: MIDNIGHT.axis }, splitLine: { lineStyle: { color: MIDNIGHT.edge } } },
    series: [mk("Senior", "senior_ending", MIDNIGHT.emerald),
             mk("Mezzanine", "mezzanine_ending", MIDNIGHT.violet),
             mk("Revolver", "revolver", MIDNIGHT.amber)],
  };
}
