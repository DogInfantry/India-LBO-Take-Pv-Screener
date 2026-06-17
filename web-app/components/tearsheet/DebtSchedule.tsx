import { cr } from "@/lib/format";
import type { DebtScheduleRow } from "@/lib/types";

const LINES: [keyof DebtScheduleRow, string][] = [
  ["ebitda", "EBITDA"], ["interest", "Interest"], ["fcf_for_debt", "FCF for debt"],
  ["senior_ending", "Senior o/s"], ["mezzanine_ending", "Mezz o/s"], ["ending_debt", "Total debt"],
];

export function DebtSchedule({ rows }: { rows: DebtScheduleRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-right text-xs font-mono">
        <thead>
          <tr className="text-faint">
            <th className="py-1 text-left font-normal">Debt schedule</th>
            {rows.map((r) => <th key={r.year} className="py-1 font-normal">Y{r.year}</th>)}
          </tr>
        </thead>
        <tbody>
          {LINES.map(([key, label]) => (
            <tr key={String(key)} className="border-t border-edge/50">
              <td className="py-1 text-left text-muted">{label}</td>
              {rows.map((r) => <td key={r.year} className="py-1 text-ink">{cr(r[key] as number)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
