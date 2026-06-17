import { cr, pct } from "@/lib/format";
import type { SourcesUses as T } from "@/lib/types";

export function SourcesUses({ su }: { su: T }) {
  const rows: [string, string][] = [
    ["Enterprise value", cr(su.enterprise_value)],
    ...su.tranches.map((t): [string, string] =>
      [`${t.name[0].toUpperCase()}${t.name.slice(1)} debt`, `${cr(t.amount)} (${pct(t.pct_of_ev, 0)} EV)`]),
    ["Transaction fees", cr(su.txn_fees)],
    ["Financing fees", cr(su.financing_fees)],
    ["Sponsor equity", cr(su.sponsor_equity)],
  ];
  return (
    <table className="w-full text-xs font-mono">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k} className="border-t border-edge/50">
            <td className="py-1 text-muted">{k}</td>
            <td className="py-1 text-right text-ink">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
