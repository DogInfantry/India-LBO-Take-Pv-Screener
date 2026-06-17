import { it, expect } from "vitest";
import { buildFrontierOption } from "@/lib/charts/frontier";

const iso = { target_irr: 0.2, points: [
  { exit_multiple: 8.7, premium_pct: 4.85 }, { exit_multiple: 10.7, premium_pct: 18.02 } ] };

it("maps frontier points to an [exit_multiple, premium] line series", () => {
  const o: any = buildFrontierOption(iso);
  expect(o.series[0].type).toBe("line");
  expect(o.series[0].data).toEqual([[8.7, 4.85], [10.7, 18.02]]);
});
