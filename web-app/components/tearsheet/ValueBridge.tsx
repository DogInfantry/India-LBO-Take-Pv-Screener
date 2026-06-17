"use client";
import { buildValueBridgeOption } from "@/lib/charts/valueBridge";
import { EChart } from "@/components/EChart";
import type { ValueBridge as T } from "@/lib/types";

export function ValueBridge({ bridge }: { bridge: T }) {
  return <EChart option={buildValueBridgeOption(bridge)} height={200} />;
}
