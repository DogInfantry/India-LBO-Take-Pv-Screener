import type { EChartsOption } from "echarts";
import { MIDNIGHT, baseOption } from "@/lib/theme";
import type { Tornado } from "@/lib/types";

const pp = (v: number) => `${(v * 100).toFixed(1)}%`;

export function buildTornadoOption(t: Tornado): EChartsOption {
  const base = t.base_irr ?? 0;
  // keep drivers with both ends present; sort by swing ascending so the widest
  // bar lands at the top (ECharts category index 0 renders at the bottom).
  const rows = t.drivers
    .filter((d) => d.low != null && d.high != null)
    .map((d) => {
      const lo = Math.min(d.low as number, d.high as number);
      const hi = Math.max(d.low as number, d.high as number);
      return { name: d.name, lo, hi, swing: hi - lo };
    })
    .sort((a, b) => a.swing - b.swing);

  const cats = rows.map((r) => r.name);
  const offset = rows.map((r) => r.lo);                                   // transparent spacer to bar start
  const downSpan = rows.map((r) => Math.max(0, Math.min(r.hi, base) - r.lo)); // lo -> base (downside)
  const upSpan = rows.map((r) => Math.max(0, r.hi - Math.max(r.lo, base)));   // base -> hi (upside)

  return {
    ...baseOption,
    grid: { ...baseOption.grid, top: 30 },
    title: {
      text: "IRR swing · P10–P90, one-at-a-time", left: 0, top: 2,
      textStyle: { color: MIDNIGHT.muted, fontSize: 11, fontWeight: "normal" as const,
                   fontFamily: "ui-monospace, monospace" },
    },
    tooltip: {
      ...baseOption.tooltip, trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (ps: any) => {
        const r = rows[ps[0].dataIndex];
        return `${r.name}<br/>low ${pp(r.lo)} · base ${pp(base)} · high ${pp(r.hi)}`
          + `<br/>swing ${pp(r.swing)}`;
      },
    },
    xAxis: {
      type: "value",
      axisLabel: { color: MIDNIGHT.axis, formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
      splitLine: { lineStyle: { color: MIDNIGHT.edge } },
    },
    yAxis: { type: "category", data: cats, axisLabel: { color: MIDNIGHT.muted } },
    series: [
      { name: "off", type: "bar", stack: "t", silent: true,
        itemStyle: { color: "transparent" }, data: offset },
      { name: "downside", type: "bar", stack: "t", data: downSpan,
        itemStyle: { color: MIDNIGHT.danger } },
      { name: "upside", type: "bar", stack: "t", data: upSpan,
        itemStyle: { color: MIDNIGHT.emerald, borderRadius: [0, 2, 2, 0] },
        markLine: {
          symbol: "none", silent: true,
          lineStyle: { color: MIDNIGHT.amber, type: "dashed" },
          label: { show: true, formatter: `base ${pp(base)}`, position: "end",
                   color: MIDNIGHT.muted, fontSize: 9 },
          data: [{ xAxis: base }],
        } },
    ],
  };
}
