"use client";
import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

type EventMap = Record<string, (params: any) => void>;

export function EChart({ option, height = 200, onEvents }: {
  option: EChartsOption; height?: number; onEvents?: EventMap;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" }); // crisp, export-safe
    chart.setOption(option);
    if (onEvents) {
      for (const [event, handler] of Object.entries(onEvents)) {
        chart.on(event, handler);
      }
    }
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); chart.dispose(); };
  }, [option, onEvents]);
  return <div ref={ref} style={{ height, width: "100%", cursor: onEvents?.click ? "pointer" : undefined }} />;
}
