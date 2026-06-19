import { loadResults } from "@/lib/data";
import { loadCompany } from "@/lib/company";
import { Section } from "@/components/tearsheet/Section";
import { Summary } from "@/components/tearsheet/Summary";
import { SourcesUses } from "@/components/tearsheet/SourcesUses";
import { IrrBridge } from "@/components/tearsheet/IrrBridge";
import { ValueBridge } from "@/components/tearsheet/ValueBridge";
import { McHistogram } from "@/components/tearsheet/McHistogram";
import { StatCards } from "@/components/tearsheet/StatCards";
import { SensitivityHeatmap } from "@/components/tearsheet/SensitivityHeatmap";
import { SobolDrivers } from "@/components/SobolDrivers";
import { StatementTable } from "@/components/tearsheet/StatementTable";
import { DebtWaterfall } from "@/components/tearsheet/DebtWaterfall";
import { DebtSchedule } from "@/components/tearsheet/DebtSchedule";
import { SolverCards } from "@/components/tearsheet/SolverCards";
import { DelistingCard } from "@/components/tearsheet/DelistingCard";
import { FeasibilityBreakdown } from "@/components/tearsheet/FeasibilityBreakdown";
import { DegenerateNotice } from "@/components/tearsheet/DegenerateNotice";
import { ScenarioWarRoom } from "@/components/tearsheet/ScenarioWarRoom";
import { pct, mult } from "@/lib/format";

export function generateStaticParams() {
  return loadResults().passers.map((p) => ({ ticker: p.ticker }));
}

const IS_LINES: [string, string][] = [["revenue", "Revenue"], ["ebitda", "EBITDA"], ["ebit", "EBIT"],
  ["interest", "Interest"], ["taxes", "Taxes"], ["net_income", "Net income"]];
const CF_LINES: [string, string][] = [["cfo", "CFO"], ["capex", "Capex"], ["fcf_for_debt", "FCF for debt"],
  ["principal_repaid", "Debt repaid"], ["ending_cash", "Ending cash"]];
const BS_LINES: [string, string][] = [["cash", "Cash"], ["nwc", "NWC"], ["ppe", "PP&E"], ["goodwill", "Goodwill"],
  ["debt", "Debt"], ["equity", "Equity"], ["assets", "Assets"]];

export default async function TearSheet({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const r = loadResults();
  const co = loadCompany(ticker);
  if (!co) return <main className="p-6 text-muted">Unknown ticker.</main>;
  const hurdle = r.config.hurdle_irr;

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-6">
      <a href="/" className="font-mono text-xs text-faint hover:text-ink">← dashboard</a>
      <Summary co={co} asOf={r.as_of} />

      <Section title="Capital structure — sources &amp; uses">
        <SourcesUses su={co.sources_uses} />
      </Section>

      {co.returns.degenerate ? <DegenerateNotice /> : (
        <>
          <Section title="Returns attribution">
            <div className="grid gap-4 lg:grid-cols-2">
              {co.returns.irr_bridge && <IrrBridge bridge={co.returns.irr_bridge} />}
              {co.returns.value_bridge && <ValueBridge bridge={co.returns.value_bridge} />}
            </div>
          </Section>

          {co.scenarios && (
            <Section title="Scenario war room — Bull / Base / Bear">
              <ScenarioWarRoom scenarios={co.scenarios} />
            </Section>
          )}

          <Section title="Risk — Monte Carlo (5,000 sims)">
            {co.montecarlo && <McHistogram samples={co.montecarlo.irr} hurdle={hurdle} />}
            {co.downside && co.montecarlo && (
              <div className="mt-3">
                <StatCards tiles={[
                  { label: "P(beat hurdle)", value: pct(co.montecarlo.p_beat_hurdle, 0), accent: "emerald" },
                  { label: "P(loss)", value: pct(co.downside.p_loss, 1) },
                  { label: "5% VaR (MOIC)", value: mult(co.downside.var5_moic) },
                  { label: "CVaR (MOIC)", value: mult(co.downside.cvar5_moic) },
                ]} />
              </div>
            )}
          </Section>

          <Section title="Sensitivity — premium × exit (IRR), with break-even frontier">
            <div className="grid gap-4 lg:grid-cols-2">
              {co.sensitivity && (
                <SensitivityHeatmap grid={co.sensitivity.grid} iso={co.sensitivity.iso_frontier} hurdle={hurdle} />
              )}
              {co.sobol && <SobolDrivers sobol={co.sobol} />}
            </div>
          </Section>

          <Section title="Operating model — three statements">
            {co.statements && (
              <div className="space-y-5">
                <StatementTable title="Income statement (₹cr)" rows={co.statements.income} lines={IS_LINES} startYear={1} />
                <StatementTable title="Cash flow (₹cr)" rows={co.statements.cash_flow} lines={CF_LINES} startYear={1} />
                <StatementTable title="Balance sheet (₹cr)" rows={co.statements.balance_sheet} lines={BS_LINES} startYear={0} />
              </div>
            )}
          </Section>

          <Section title="Debt — paydown &amp; capacity">
            <div className="space-y-4">
              {co.debt_schedule && <DebtWaterfall schedule={co.debt_schedule} />}
              {co.debt_schedule && <DebtSchedule rows={co.debt_schedule} />}
              {co.solvers && <SolverCards solvers={co.solvers} />}
            </div>
          </Section>
        </>
      )}

      <Section title="Take-private / deal">
        <div className="grid gap-4 lg:grid-cols-2">
          <DelistingCard d={co.delisting} />
          <FeasibilityBreakdown f={co.feasibility} />
        </div>
      </Section>
    </main>
  );
}
