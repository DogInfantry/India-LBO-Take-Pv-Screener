export function StatCards(
  { tiles }: { tiles: { label: string; value: string; accent?: "emerald" | "violet" | "amber" }[] }
) {
  const color = (a?: string) =>
    a === "violet" ? "text-violet" : a === "amber" ? "text-amber" : a === "emerald" ? "text-emerald" : "text-ink";
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-md border border-edge bg-bg/40 px-3 py-2">
          <div className={`font-mono text-base leading-tight ${color(t.accent)}`}>{t.value}</div>
          <div className="text-[10px] uppercase tracking-wide text-faint">{t.label}</div>
        </div>
      ))}
    </div>
  );
}
