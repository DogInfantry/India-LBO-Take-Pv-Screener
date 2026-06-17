"use client";
import { buildMcHistogramOption } from "@/lib/charts/mcHistogram";
import { EChart } from "@/components/EChart";

export function McHistogram({ samples, hurdle }: { samples: (number | null)[]; hurdle: number }) {
  const xs = samples.filter((x): x is number => x != null);
  return <EChart option={buildMcHistogramOption(xs, hurdle)} height={200} />;
}
