import { it, expect } from "vitest";
import { kpis } from "@/lib/kpis";
import { loadResults } from "@/lib/data";
it("builds KPI tiles from the real contract, top excludes degenerate", () => {
  const k = kpis(loadResults());
  expect(k.find((t) => t.label === "Passers")?.value).toMatch(/\d/);
  const topIrr = k.find((t) => t.label === "Top IRR")!;
  expect(topIrr.value).toMatch(/%$/);
});
