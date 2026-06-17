import { mult } from "@/lib/format";
import type { Solvers } from "@/lib/types";

function Card({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-md border border-edge bg-bg/40 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-faint">{label}</div>
      <div className="font-mono text-base text-ink">{value}</div>
      {sub && <div className="text-[10px] text-muted">{sub}</div>}
    </div>
  );
}

export function SolverCards({ solvers }: { solvers: Solvers }) {
  const mb = solvers.max_bid;
  const dc = solvers.debt_capacity;
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      <Card label="Max bid (clears hurdle)"
        value={mb.converged && mb.max_premium_pct != null ? `${mb.max_premium_pct.toFixed(0)}% premium` : "n.m."}
        sub={mb.converged ? undefined : "cannot clear hurdle at any premium"} />
      <Card label="Max sustainable leverage"
        value={dc.converged && dc.max_leverage != null ? mult(dc.max_leverage) : "n.m."}
        sub={dc.min_coverage_at_max != null ? `min coverage ${dc.min_coverage_at_max.toFixed(1)}x` : undefined} />
      <Card label="Optimal exit"
        value={solvers.optimal_exit.best_year != null ? `Year ${solvers.optimal_exit.best_year}` : "n.m."} />
    </div>
  );
}
