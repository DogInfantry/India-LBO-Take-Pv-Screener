"use client";
import { buildHoldPeriodOption } from "@/lib/charts/holdPeriod";
import { EChart } from "@/components/EChart";
import type { Results } from "@/lib/types";

export function HoldPeriodCurves({ results }: { results: Results }) {
  const hurdle = results.config.hurdle_irr;
  const series = results.passers
    .filter((p) => !p.degenerate)
    .map((p) => {
      const co = results.companies[p.ticker];
      const byYear = co?.solvers?.optimal_exit?.by_year ?? [];
      return {
        name: p.ticker.replace(".NS", ""),
        ticker: p.ticker,
        data: byYear.map((r) => ({ year: r.year, irr: r.irr })),
      };
    })
    .filter((s) => s.data.length > 0);

  if (series.length === 0) return null;
  return <EChart option={buildHoldPeriodOption(series, hurdle)} height={220} />;
}
