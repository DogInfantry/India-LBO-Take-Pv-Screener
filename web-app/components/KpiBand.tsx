import type { Results } from "@/lib/types";
import { kpis } from "@/lib/kpis";

export function KpiBand({ results }: { results: Results }) {
  const tiles = kpis(results);
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-md border border-edge bg-panel px-3 py-2">
          <div className={`font-mono text-lg leading-tight ${
            t.accent === "violet" ? "text-violet" : t.accent === "emerald" ? "text-emerald" : "text-ink"}`}>
            {t.value}
          </div>
          <div className="text-[10px] uppercase tracking-wide text-faint">{t.label}</div>
        </div>
      ))}
    </div>
  );
}
