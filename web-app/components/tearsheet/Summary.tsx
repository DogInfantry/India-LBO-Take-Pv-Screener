import { pct, mult } from "@/lib/format";
import { StatCards } from "./StatCards";
import type { CompanyBlock } from "@/lib/types";

export function Summary({ co, asOf }: { co: CompanyBlock; asOf: string }) {
  const exit = co.solvers?.optimal_exit.best_year;
  return (
    <header className="space-y-3">
      <div>
        <h1 className="text-2xl font-semibold text-ink">{co.name}</h1>
        <p className="font-mono text-xs text-faint">{co.ticker} · take-private tear sheet · as of {asOf}</p>
      </div>
      <StatCards tiles={[
        { label: "Base-case IRR", value: pct(co.returns.irr), accent: "emerald" },
        { label: "MOIC", value: mult(co.returns.moic), accent: "emerald" },
        { label: "Optimal exit", value: exit != null ? `Year ${exit}` : "n.m.", accent: "amber" },
        { label: "Feasibility", value: String(co.feasibility.score), accent: "violet" },
      ]} />
    </header>
  );
}
