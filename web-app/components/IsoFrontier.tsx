"use client";
import { buildFrontierOption } from "@/lib/charts/frontier";
import { EChart } from "./EChart";
import type { IsoFrontierPoint } from "@/lib/types";

export function IsoFrontier({ iso }: { iso: { target_irr: number; points: IsoFrontierPoint[] } }) {
  return <EChart option={buildFrontierOption(iso)} height={200} />;
}
