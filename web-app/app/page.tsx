import { loadResults } from "@/lib/data";
import { KpiBand } from "@/components/KpiBand";
import { IrrLeaderboard } from "@/components/IrrLeaderboard";
import { IsoFrontier } from "@/components/IsoFrontier";
import { FeasibilityPanel } from "@/components/FeasibilityPanel";
import { SobolDrivers } from "@/components/SobolDrivers";
import { WarRoomTable } from "@/components/WarRoomTable";
import { HoldPeriodCurves } from "@/components/HoldPeriodCurves";

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-edge bg-panel p-3">
      <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wider text-faint">{title}</h2>
      {children}
    </section>
  );
}

export default function Page() {
  const r = loadResults();
  // highest-IRR live name drives the single-company panels (order-independent)
  const top = [...r.passers].filter((p) => !p.degenerate && p.irr != null)
                .sort((a, b) => b.irr! - a.irr!)[0] ?? r.passers[0];
  const topCo = r.companies[top.ticker];
  return (
    <main className="mx-auto max-w-6xl p-6">
      <header className="mb-4 flex items-baseline justify-between">
        <h1 className="font-mono text-sm tracking-[0.2em] text-faint">
          INDIA LBO TAKE-PRIVATE SCREENER · AS OF {r.as_of.toUpperCase()}
        </h1>
        <a href="/compare" className="font-mono text-xs text-faint hover:text-emerald">
          compare all →
        </a>
      </header>
      <KpiBand results={r} />
      <div className="mt-3">
        <Panel title="Scenario war room — Bull / Base / Bear">
          <WarRoomTable passers={r.passers} />
        </Panel>
      </div>
      <div className="mt-3">
        <Panel title="Hold-period return curves — IRR by exit year">
          <HoldPeriodCurves results={r} />
        </Panel>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel title="Base-case IRR — ranked"><IrrLeaderboard passers={r.passers} hurdle={r.config.hurdle_irr} /></Panel>
        <Panel title={`Iso-IRR frontier · ${top.name}`}>
          {topCo.sensitivity ? <IsoFrontier iso={topCo.sensitivity.iso_frontier} /> : null}
        </Panel>
        <Panel title="Take-private feasibility"><FeasibilityPanel passers={r.passers} /></Panel>
        <Panel title={`IRR variance drivers (Sobol) · ${top.name}`}>
          {topCo.sobol ? <SobolDrivers sobol={topCo.sobol} /> : null}
        </Panel>
      </div>
    </main>
  );
}
