import type { ScenarioBlock, Scenario } from "@/lib/types";
import { pct, mult, cr } from "@/lib/format";

interface Props { scenarios: ScenarioBlock | null; }

function irrColor(irr: number | null): string {
  if (irr == null) return "text-muted";
  if (irr >= 0.20) return "text-green-600";
  if (irr >= 0.10) return "text-amber-600";
  return "text-red-600";
}

interface RowProps { label: string; bull: string; base: string; bear: string; bullClass?: string; baseClass?: string; bearClass?: string; }
function Row({ label, bull, base, bear, bullClass = "", baseClass = "", bearClass = "" }: RowProps) {
  return (
    <tr className="border-t border-edge text-[11px]">
      <td className="py-1 pr-3 font-mono text-faint">{label}</td>
      <td className={`py-1 text-center bg-green-50 ${bullClass}`}>{bull}</td>
      <td className={`py-1 text-center ${baseClass}`}>{base}</td>
      <td className={`py-1 text-center bg-red-50 ${bearClass}`}>{bear}</td>
    </tr>
  );
}

function SectionHeader({ label }: { label: string }) {
  return (
    <tr>
      <td colSpan={4} className="pt-3 pb-1 font-mono text-[10px] uppercase tracking-wider text-faint">{label}</td>
    </tr>
  );
}

function fmt(s: Scenario | null, fn: (s: Scenario) => string): string {
  return s ? fn(s) : "—";
}

export function ScenarioWarRoom({ scenarios }: Props) {
  if (!scenarios) return null;
  const { bull, base, bear } = scenarios;

  return (
    <table className="w-full">
      <thead>
        <tr className="text-[11px]">
          <th className="w-28 text-left font-mono text-faint" />
          <th className="text-center font-mono text-green-600">BULL</th>
          <th className="text-center font-mono text-ink">BASE</th>
          <th className="text-center font-mono text-red-600">BEAR</th>
        </tr>
      </thead>
      <tbody>
        <SectionHeader label="Assumptions" />
        <Row label="Rev growth"
          bull={fmt(bull, s => pct(s.assumptions.revenue_growth, 0))}
          base={fmt(base, s => pct(s.assumptions.revenue_growth, 0))}
          bear={fmt(bear, s => pct(s.assumptions.revenue_growth, 0))} />
        <Row label="Margin"
          bull={fmt(bull, s => pct(s.assumptions.ebitda_margin, 0))}
          base={fmt(base, s => pct(s.assumptions.ebitda_margin, 0))}
          bear={fmt(bear, s => pct(s.assumptions.ebitda_margin, 0))} />
        <Row label="Exit multiple"
          bull={fmt(bull, s => `${s.assumptions.exit_multiple.toFixed(1)}x`)}
          base={fmt(base, s => `${s.assumptions.exit_multiple.toFixed(1)}x`)}
          bear={fmt(bear, s => `${s.assumptions.exit_multiple.toFixed(1)}x`)} />

        <SectionHeader label="Financials at exit (₹cr)" />
        <Row label="Revenue"
          bull={fmt(bull, s => cr(s.financials.revenue))}
          base={fmt(base, s => cr(s.financials.revenue))}
          bear={fmt(bear, s => cr(s.financials.revenue))} />
        <Row label="EBITDA"
          bull={fmt(bull, s => cr(s.financials.ebitda))}
          base={fmt(base, s => cr(s.financials.ebitda))}
          bear={fmt(bear, s => cr(s.financials.ebitda))} />
        <Row label="FCF"
          bull={fmt(bull, s => cr(s.financials.fcf_for_debt))}
          base={fmt(base, s => cr(s.financials.fcf_for_debt))}
          bear={fmt(bear, s => cr(s.financials.fcf_for_debt))} />

        <SectionHeader label="Returns" />
        <Row label="IRR"
          bull={fmt(bull, s => s.returns.irr == null ? "—" : pct(s.returns.irr, 1))}
          base={fmt(base, s => s.returns.irr == null ? "—" : pct(s.returns.irr, 1))}
          bear={fmt(bear, s => s.returns.irr == null ? "—" : pct(s.returns.irr, 1))}
          bullClass={bull ? irrColor(bull.returns.irr) + " font-bold text-sm" : ""}
          baseClass={base ? irrColor(base.returns.irr) + " font-bold text-sm" : ""}
          bearClass={bear ? irrColor(bear.returns.irr) + " font-bold text-sm" : ""} />
        <Row label="MOIC"
          bull={fmt(bull, s => mult(s.returns.moic))}
          base={fmt(base, s => mult(s.returns.moic))}
          bear={fmt(bear, s => mult(s.returns.moic))} />
        <Row label="Exit equity"
          bull={fmt(bull, s => cr(s.returns.exit_equity))}
          base={fmt(base, s => cr(s.returns.exit_equity))}
          bear={fmt(bear, s => cr(s.returns.exit_equity))} />
      </tbody>
    </table>
  );
}
