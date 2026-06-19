import { it, expect } from "vitest";
import { buildHoldPeriodOption } from "@/lib/charts/holdPeriod";

const series = [
  { name: "NATCO", ticker: "NATCOPHARM.NS",
    data: [1,2,3,4,5].map(year => ({ year, irr: 0.10 + year * 0.01 })) },
  { name: "ZENSAR", ticker: "ZENSARTECH.NS",
    data: [1,2,3,4,5].map(year => ({ year, irr: 0.09 + year * 0.01 })) },
];

it("includes a hurdle series and one series per company", () => {
  const o: any = buildHoldPeriodOption(series, 0.20);
  const names = o.series.map((s: any) => s.name);
  expect(names).toContain("20% hurdle");
  expect(names).toContain("NATCO");
  expect(names).toContain("ZENSAR");
});

it("hurdle series has constant value", () => {
  const o: any = buildHoldPeriodOption(series, 0.20);
  const h = o.series.find((s: any) => s.name === "20% hurdle");
  expect(h.data.every((v: number) => v === 0.20)).toBe(true);
  expect(h.lineStyle.type).toBe("dashed");
});

it("company IRR values match input data", () => {
  const o: any = buildHoldPeriodOption(series, 0.20);
  const natco = o.series.find((s: any) => s.name === "NATCO");
  expect(natco.data[0]).toBeCloseTo(0.11);
  expect(natco.data[4]).toBeCloseTo(0.15);
});
