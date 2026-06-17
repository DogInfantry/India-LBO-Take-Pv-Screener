import { it, expect } from "vitest";
import { loadCompany } from "@/lib/company";
import { loadResults } from "@/lib/data";

it("loads a healthy company block with detail fields typed", () => {
  const top = loadResults().passers.find((p) => !p.degenerate)!;
  const co = loadCompany(top.ticker)!;
  expect(co.statements!.income.length).toBe(5);
  expect(co.statements!.balance_sheet.length).toBe(6);   // year 0..5
  expect(co.sensitivity!.grid.irr.length).toBeGreaterThan(0);
  expect(co.solvers!.optimal_exit.best_year).toBeGreaterThanOrEqual(1);
});

it("returns a degenerate block with null LBO sections", () => {
  const d = loadResults().passers.find((p) => p.degenerate)!;
  const co = loadCompany(d.ticker)!;
  expect(co.returns.degenerate).toBe(true);
  expect(co.statements).toBeNull();
});
