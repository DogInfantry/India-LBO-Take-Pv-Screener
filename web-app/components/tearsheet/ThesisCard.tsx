import type { CompanyBlock } from "@/lib/types";

const cr = (v: number) => `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })} cr`;
const pp = (v: number) => `${(v * 100).toFixed(1)}%`;
const x = (v: number) => `${v.toFixed(1)}×`;

export function ThesisCard({ co }: { co: CompanyBlock }) {
  const sm = co.screener_metrics;
  const holding = co.delisting.promoter_holding_pct;
  const headroom = 75 - holding;
  const netLevMult = sm.net_debt_cr / sm.ebitda_cr;
  // years to repay entry debt from FCF (illustrative, flat FCF)
  const entryDebt = co.sources_uses.debt;
  const fcfYear1 = sm.fcf_cr;
  const paybackYrs = fcfYear1 > 0 ? (entryDebt / fcfYear1).toFixed(1) : "—";

  const bullets: string[] = [
    `${cr(sm.unused_debt_capacity_cr)} of unused leverage headroom to the 3× EBITDA RBI ceiling ` +
      `(net debt today: ${x(Math.max(0, netLevMult))} EBITDA)`,
    `FCF yield ${pp(sm.fcf_yield)} — at flat FCF the full debt stack is repayable in ~${paybackYrs} years`,
    `Promoter at ${holding.toFixed(1)}%, ${headroom.toFixed(1)}pp below the SEBI 75% take-private ` +
      `cap — acquisition-finance runway intact under RBI April 2026 rules`,
    `FY${sm.latest_year}: ${cr(sm.revenue_cr)} revenue · ${pp(sm.ebitda_margin)} EBITDA margin · ` +
      `${x(sm.interest_coverage)} interest coverage`,
  ];

  return (
    <div className="rounded border border-edge bg-panel p-4 font-mono text-xs">
      <p className="mb-2 text-faint uppercase tracking-widest text-[10px]">LBO thesis</p>
      <ul className="space-y-2">
        {bullets.map((b, i) => (
          <li key={i} className="flex gap-2 text-muted leading-relaxed">
            <span className="text-emerald shrink-0">›</span>
            <span>{b}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
