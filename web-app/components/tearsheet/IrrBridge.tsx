"use client";
import { buildIrrBridgeOption } from "@/lib/charts/irrBridge";
import { EChart } from "@/components/EChart";
import type { IrrBridge as T } from "@/lib/types";

export function IrrBridge({ bridge }: { bridge: T }) {
  return <EChart option={buildIrrBridgeOption(bridge)} height={200} />;
}
