import { it, expect } from "vitest";
import { buildIrrBridgeOption } from "@/lib/charts/irrBridge";
const br = { deleveraging: 0.056, ebitda_growth: 0.101, multiple_rerating: 0.0, total_irr: 0.157 };
it("renders a 4-bar cumulative waterfall ending at total IRR", () => {
  const o: any = buildIrrBridgeOption(br);
  expect(o.xAxis.data).toEqual(["Deleveraging", "EBITDA growth", "Multiple re-rating", "Total IRR"]);
  const vis = o.series.find((s: any) => s.name === "value").data;
  expect(vis[vis.length - 1]).toBeCloseTo(0.157);
});
