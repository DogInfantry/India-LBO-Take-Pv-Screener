import { cr } from "@/lib/format";

export function StatementTable(
  { title, rows, lines, startYear = 1 }:
  { title: string; rows: Record<string, number>[]; lines: [string, string][]; startYear?: number }
) {
  void startYear;
  const years = rows.map((r) => `Y${r.year ?? ""}`);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-right text-xs font-mono">
        <thead>
          <tr className="text-faint">
            <th className="py-1 text-left font-normal">{title}</th>
            {years.map((y, i) => <th key={i} className="py-1 font-normal">{y}</th>)}
          </tr>
        </thead>
        <tbody>
          {lines.map(([key, label]) => (
            <tr key={key} className="border-t border-edge/50">
              <td className="py-1 text-left text-muted">{label}</td>
              {rows.map((r, i) => <td key={i} className="py-1 text-ink">{cr(r[key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
