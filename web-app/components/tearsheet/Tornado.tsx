"use client";
import { buildTornadoOption } from "@/lib/charts/tornado";
import { EChart } from "@/components/EChart";
import type { Tornado as T } from "@/lib/types";

export function Tornado({ tornado }: { tornado: T }) {
  return <EChart option={buildTornadoOption(tornado)} height={200} />;
}
