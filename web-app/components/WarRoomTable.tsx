import Link from "next/link";
import type { Passer } from "@/lib/types";
import { pct } from "@/lib/format";

interface Props { passers: Passer[]; }

function irrCell(irr: number | null): { text: string; cls: string } {
  if (irr == null) return { text: "—", cls: "text-muted" };
  const text = pct(irr, 1);
  const cls = irr >= 0.20 ? "text-green-600 font-semibold"
             : irr >= 0.10 ? "text-amber-600"
             : "text-red-600";
  return { text, cls };
}

export function WarRoomTable({ passers }: Props) {
  const hasAny = passers.some(p => p.scenario_irrs != null);
  if (!hasAny) return null;

  const sorted = [...passers].sort((a, b) => {
    const ai = a.scenario_irrs?.base ?? -Infinity;
    const bi = b.scenario_irrs?.base ?? -Infinity;
    return bi - ai;
  });

  return (
    <table className="w-full text-[11px]">
      <thead>
        <tr className="border-b border-edge">
          <th className="pb-1 text-left font-mono text-faint">Company</th>
          <th className="pb-1 text-center font-mono text-green-600">BULL</th>
          <th className="pb-1 text-center font-mono text-ink">BASE</th>
          <th className="pb-1 text-center font-mono text-red-600">BEAR</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map(p => {
          const si = p.scenario_irrs;
          const bull = irrCell(si?.bull ?? null);
          const base = irrCell(si?.base ?? null);
          const bear = irrCell(si?.bear ?? null);
          return (
            <tr key={p.ticker} className="border-t border-edge hover:bg-panel">
              <td className="py-1 pr-3">
                <Link href={`/t/${p.ticker}`} className="font-mono hover:text-emerald">
                  {p.ticker}
                </Link>
                <span className="ml-1 text-faint">{p.name}</span>
              </td>
              <td className={`py-1 text-center ${bull.cls}`}>{bull.text}</td>
              <td className={`py-1 text-center ${base.cls}`}>{base.text}</td>
              <td className={`py-1 text-center ${bear.cls}`}>{bear.text}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
