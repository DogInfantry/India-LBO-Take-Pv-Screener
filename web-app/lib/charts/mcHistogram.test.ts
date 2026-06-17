import { it, expect } from "vitest";
import { buildMcHistogramOption } from "@/lib/charts/mcHistogram";
const irr = Array.from({ length: 1000 }, (_, i) => (i % 40) / 100);   // 0..0.39 spread
it("bins the samples and marks the hurdle", () => {
  const o: any = buildMcHistogramOption(irr.filter((x) => x != null) as number[], 0.20, 20);
  const counts = o.series[0].data as any[];
  expect(counts.length).toBe(20);
  const total = counts.reduce((a: number, c: any) => a + (Array.isArray(c) ? c[1] : c.value ?? c), 0);
  expect(total).toBe(1000);
  // hurdle marker sits on a bin index (category axis) and is labelled "hurdle …"
  expect(typeof o.series[0].markLine.data[0].xAxis).toBe("number");
  expect(JSON.stringify(o.series[0].markLine.label)).toContain("hurdle");
});
