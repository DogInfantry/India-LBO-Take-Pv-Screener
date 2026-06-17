import { it, expect } from "vitest";
import { buildFeasibilityOption } from "@/lib/charts/feasibility";
import type { Passer } from "@/lib/types";
const ps: Passer[] = [
  { ticker:"A.NS",name:"A",irr:.1,moic:1.5,degenerate:false,feasibility:96,max_bid_premium_pct:null },
  { ticker:"B.NS",name:"B",irr:.1,moic:1.5,degenerate:false,feasibility:87,max_bid_premium_pct:null },
];
it("ranks feasibility descending (top bar highest)", () => {
  const o: any = buildFeasibilityOption(ps);
  expect(o.yAxis.data).toEqual(["B", "A"]);        // asc so A on top
  expect(Math.max(...o.series[0].data)).toBe(96);
});
