"use client";
import { buildSobolOption } from "@/lib/charts/sobol";
import { EChart } from "./EChart";
export function SobolDrivers({ sobol }: { sobol: { total_order: Record<string, number> } }) {
  return <EChart option={buildSobolOption(sobol)} height={160} />;
}
