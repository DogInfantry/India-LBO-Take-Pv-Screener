import { it, expect } from "vitest";
import { buildSobolOption } from "@/lib/charts/sobol";
const sobol = { first_order: {}, total_order: { revenue_growth: 0.41, exit_multiple: 0.39, ebitda_shock: 0.20 } };
it("ranks drivers by total-order variance share, descending top bar", () => {
  const o: any = buildSobolOption(sobol);
  expect(o.yAxis.data[o.yAxis.data.length - 1]).toBe("revenue_growth"); // top = highest
  expect(Math.max(...o.series[0].data)).toBeCloseTo(0.41);
});
