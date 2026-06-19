import { loadResults } from "@/lib/data";
import { pct, mult, cr } from "@/lib/format";
import type { CompanyBlock, Passer } from "@/lib/types";

interface Row {
  label: string;
  fmt: (co: CompanyBlock, p: Passer) => string;
  higherIsBetter: boolean; // for green/red coding
}

const ROWS: Row[] = [
  { label: "Base-case IRR",        fmt: (c) => pct(c.returns.irr),                    higherIsBetter: true  },
  { label: "MOIC",                 fmt: (c) => mult(c.returns.moic),                   higherIsBetter: true  },
  { label: "Entry EV",             fmt: (c) => cr(c.sources_uses.enterprise_value),    higherIsBetter: false },
  { label: "EV / entry EBITDA",    fmt: (c) => mult(c.sources_uses.enterprise_value / c.screener_metrics.ebitda_cr, 1), higherIsBetter: false },
  { label: "Unused debt capacity", fmt: (c) => cr(c.screener_metrics.unused_debt_capacity_cr), higherIsBetter: true  },
  { label: "FCF yield",            fmt: (c) => pct(c.screener_metrics.fcf_yield),      higherIsBetter: true  },
  { label: "EBITDA margin",        fmt: (c) => pct(c.screener_metrics.ebitda_margin),  higherIsBetter: true  },
  { label: "Interest coverage",    fmt: (c) => `${c.screener_metrics.interest_coverage.toFixed(1)}×`, higherIsBetter: true },
  { label: "P(beat 20% hurdle)",   fmt: (c) => c.montecarlo ? pct(c.montecarlo.p_beat_hurdle) : "—", higherIsBetter: true },
  { label: "Max bid premium",      fmt: (_c, p) => p.max_bid_premium_pct != null ? `${p.max_bid_premium_pct.toFixed(1)}%` : "—", higherIsBetter: true },
  { label: "Feasibility score",    fmt: (_c, p) => `${p.feasibility}/100`,             higherIsBetter: true  },
  { label: "Promoter holding",     fmt: (c) => `${c.delisting.promoter_holding_pct.toFixed(1)}%`, higherIsBetter: false },
];

function rawValue(row: Row, co: CompanyBlock, p: Passer): number | null {
  // Extract a comparable numeric value for min/max ranking
  if (row.label === "Base-case IRR")        return co.returns.irr;
  if (row.label === "MOIC")                 return co.returns.moic;
  if (row.label === "Entry EV")             return co.sources_uses.enterprise_value;
  if (row.label === "EV / entry EBITDA")    return co.sources_uses.enterprise_value / co.screener_metrics.ebitda_cr;
  if (row.label === "Unused debt capacity") return co.screener_metrics.unused_debt_capacity_cr;
  if (row.label === "FCF yield")            return co.screener_metrics.fcf_yield;
  if (row.label === "EBITDA margin")        return co.screener_metrics.ebitda_margin;
  if (row.label === "Interest coverage")    return co.screener_metrics.interest_coverage;
  if (row.label === "P(beat 20% hurdle)")   return co.montecarlo?.p_beat_hurdle ?? null;
  if (row.label === "Max bid premium")      return p.max_bid_premium_pct;
  if (row.label === "Feasibility score")    return p.feasibility;
  if (row.label === "Promoter holding")     return co.delisting.promoter_holding_pct;
  return null;
}

export default function ComparePage() {
  const r = loadResults();
  const live = r.passers.filter((p) => !p.degenerate);
  const cos = live.map((p) => ({ p, co: r.companies[p.ticker] }));

  return (
    <main className="mx-auto max-w-6xl p-6 font-mono">
      <a href="/" className="text-xs text-faint hover:text-ink">← dashboard</a>
      <h1 className="mt-3 mb-1 text-sm tracking-[0.2em] text-faint uppercase">
        Side-by-side · {live.length} passers
      </h1>
      <p className="mb-5 text-xs text-faint">
        All companies that clear every screen criterion. <span className="text-emerald">Green</span> = best in row · <span className="text-[#ef4444]">Red</span> = worst.
      </p>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="border-b border-edge">
              <th className="py-2 pr-4 text-left text-faint font-normal text-[10px] uppercase tracking-wider w-44">Metric</th>
              {cos.map(({ p, co }) => (
                <th key={p.ticker} className="py-2 px-3 text-center font-normal">
                  <a href={`/t/${p.ticker}`} className="text-ink hover:text-emerald">
                    {p.ticker.replace(".NS", "")}
                  </a>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const vals = cos.map(({ p, co }) => rawValue(row, co, p));
              const finite = vals.filter((v): v is number => v != null);
              const best = finite.length ? (row.higherIsBetter ? Math.max(...finite) : Math.min(...finite)) : null;
              const worst = finite.length ? (row.higherIsBetter ? Math.min(...finite) : Math.max(...finite)) : null;

              return (
                <tr key={row.label} className="border-b border-edge/50 hover:bg-panel/60">
                  <td className="py-2 pr-4 text-faint">{row.label}</td>
                  {cos.map(({ p, co }) => {
                    const v = rawValue(row, co, p);
                    const isBest  = v != null && best  != null && Math.abs(v - best)  < 1e-9;
                    const isWorst = v != null && worst != null && Math.abs(v - worst) < 1e-9 && best !== worst;
                    return (
                      <td key={p.ticker}
                          className={`py-2 px-3 text-center tabular-nums ${
                            isBest  ? "text-emerald font-medium" :
                            isWorst ? "text-[#ef4444]" : "text-muted"
                          }`}>
                        {row.fmt(co, p)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </main>
  );
}
