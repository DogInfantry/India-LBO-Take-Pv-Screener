type F = { score: number; components: Record<string, number>; weights: Record<string, number> };

export function FeasibilityBreakdown({ f }: { f: F }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline gap-2">
        <span className="font-mono text-2xl text-violet">{f.score}</span>
        <span className="text-[10px] uppercase tracking-wide text-faint">feasibility / 100</span>
      </div>
      <div className="space-y-1">
        {Object.entries(f.components).map(([k, v]) => (
          <div key={k} className="flex items-center gap-2 text-xs">
            <span className="w-20 text-muted">{k}</span>
            <div className="h-2 flex-1 rounded bg-edge">
              <div className="h-2 rounded bg-violet" style={{ width: `${Math.max(0, Math.min(100, v))}%` }} />
            </div>
            <span className="w-8 text-right font-mono text-faint">{Math.round(v)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
