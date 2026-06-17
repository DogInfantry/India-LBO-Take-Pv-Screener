import { loadResults } from "@/lib/data";

export function generateStaticParams() {
  return loadResults().passers.map((p) => ({ ticker: p.ticker }));
}

export default async function TearSheet({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const r = loadResults();
  const co = r.companies[ticker];
  if (!co) return <main className="p-6">Unknown ticker.</main>;
  const pct = (v: number | null) => (v == null ? "n.m." : `${(v * 100).toFixed(1)}%`);
  return (
    <main className="mx-auto max-w-4xl p-6">
      <a href="/" className="font-mono text-xs text-faint hover:text-ink">← dashboard</a>
      <h1 className="mt-2 text-2xl font-semibold">{co.name}</h1>
      <p className="mt-1 font-mono text-sm text-muted">
        IRR {pct(co.returns.irr)} · MOIC {co.returns.moic == null ? "n.m." : co.returns.moic.toFixed(2) + "x"}
        · feasibility {co.feasibility.score}
      </p>
      <p className="mt-6 text-sm text-faint">Full tear sheet — Phase 3.</p>
    </main>
  );
}
