import type { Results } from "./types";
import { topReturns } from "./data";

export function kpis(r: Results) {
  const t = topReturns(r.passers);
  const pct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
  return [
    { label: "Passers", value: String(r.universe.passed) },
    { label: "Screened", value: String(r.universe.screened) },
    { label: "Top IRR", value: pct(t.topIrr), accent: "emerald" },
    { label: "Top MOIC", value: t.topMoic == null ? "—" : `${t.topMoic.toFixed(2)}x`, accent: "emerald" },
    { label: "Top feasibility", value: String(t.topFeasibility), accent: "violet" },
  ];
}
