import { cr } from "@/lib/format";
import type { Delisting } from "@/lib/types";

export function DelistingCard({ d }: { d: Delisting }) {
  const rows: [string, string][] = [
    ["Acceptance threshold", `${d.acceptance_threshold_pct.toFixed(0)}%`],
    ["Promoter holding", `${d.promoter_holding_pct.toFixed(1)}%`],
    ["Public float to tender", `${d.float_to_tender_pct.toFixed(1)}%`],
    ["Indicative premium", `${d.indicative_premium_pct.toFixed(0)}%`],
    ["Indicative discovered EV", cr(d.indicative_discovered_ev_cr)],
  ];
  return (
    <div>
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
      <p className="mt-2 text-[10px] italic text-faint">{d.assumptions}</p>
    </div>
  );
}
