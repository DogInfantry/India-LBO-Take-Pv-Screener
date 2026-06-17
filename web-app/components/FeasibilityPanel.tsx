"use client";
import type { Passer } from "@/lib/types";
import { buildFeasibilityOption } from "@/lib/charts/feasibility";
import { EChart } from "./EChart";
export function FeasibilityPanel({ passers }: { passers: Passer[] }) {
  return <EChart option={buildFeasibilityOption(passers)} height={Math.max(160, 30 * passers.length)} />;
}
