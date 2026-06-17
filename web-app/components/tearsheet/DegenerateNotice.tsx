export function DegenerateNotice() {
  return (
    <div className="rounded-lg border border-amber/40 bg-amber/5 px-4 py-3">
      <p className="font-mono text-sm text-amber">n.m. — net cash &gt; market cap; LBO not computable.</p>
      <p className="mt-1 text-xs text-muted">
        Entry enterprise value is at or below zero, so the paper LBO has no meaningful
        return. Only the take-private feasibility signals (promoter, float, delisting)
        are shown below.
      </p>
    </div>
  );
}
