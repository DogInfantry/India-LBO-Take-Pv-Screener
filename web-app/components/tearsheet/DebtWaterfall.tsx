"use client";
import { buildDebtWaterfallOption } from "@/lib/charts/debtWaterfall";
import { EChart } from "@/components/EChart";
import type { DebtScheduleRow } from "@/lib/types";

export function DebtWaterfall({ schedule }: { schedule: DebtScheduleRow[] }) {
  return <EChart option={buildDebtWaterfallOption(schedule)} height={200} />;
}
