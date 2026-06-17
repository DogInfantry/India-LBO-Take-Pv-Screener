"use client";
import { buildHeatmapOption } from "@/lib/charts/heatmap";
import { EChart } from "@/components/EChart";
import type { SensitivityGrid, IsoFrontierPoint } from "@/lib/types";

export function SensitivityHeatmap({ grid, iso, hurdle }:
  { grid: SensitivityGrid; iso: { target_irr: number; points: IsoFrontierPoint[] }; hurdle: number }) {
  return <EChart option={buildHeatmapOption(grid, iso, hurdle)} height={260} />;
}
