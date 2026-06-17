import { it, expect } from "vitest";
import { buildValueBridgeOption } from "@/lib/charts/valueBridge";
const vb = { entry_equity: 8000, ebitda_growth: 5000, multiple_change: 0, debt_paydown: 3000,
             fees_and_other: -200, exit_equity: 15800 };
it("starts at entry equity and ends at exit equity", () => {
  const o: any = buildValueBridgeOption(vb);
  expect(o.xAxis.data[0]).toBe("Entry equity");
  expect(o.xAxis.data[o.xAxis.data.length - 1]).toBe("Exit equity");
  const val = o.series.find((s: any) => s.name === "value").data;
  expect(val[0]).toBeCloseTo(8000);
  expect(val[val.length - 1]).toBeCloseTo(15800);
});
