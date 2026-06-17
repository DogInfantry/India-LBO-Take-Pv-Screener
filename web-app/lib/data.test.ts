import { describe, it, expect } from "vitest";
import { loadResults, topReturns } from "@/lib/data";

describe("loadResults", () => {
  const r = loadResults();
  it("parses the real contract", () => {
    expect(r.as_of).toBeTruthy();
    expect(r.passers.length).toBeGreaterThan(0);
  });
  it("every passer has a matching company block", () => {
    for (const p of r.passers) expect(r.companies[p.ticker]).toBeDefined();
  });
  it("top IRR/MOIC exclude degenerate names", () => {
    const t = topReturns(r.passers);
    const degens = r.passers.filter((p) => p.degenerate).map((p) => p.ticker);
    expect(degens.length).toBeGreaterThan(0);          // JUSTDIAL is degenerate
    expect(t.topIrr).not.toBeNull();
    // the degenerate names never set the max
    expect(t.topIrrTicker && degens.includes(t.topIrrTicker)).toBeFalsy();
  });
});
