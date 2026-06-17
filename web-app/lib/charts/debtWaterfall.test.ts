import { it, expect } from "vitest";
import { buildDebtWaterfallOption } from "@/lib/charts/debtWaterfall";
import type { DebtScheduleRow } from "@/lib/types";
const sched = [
  { year: 1, senior_ending: 3000, mezzanine_ending: 1700, revolver: 0 },
  { year: 2, senior_ending: 2200, mezzanine_ending: 1700, revolver: 0 },
] as unknown as DebtScheduleRow[];
it("stacks senior + mezzanine + revolver per year", () => {
  const o: any = buildDebtWaterfallOption(sched);
  const names = o.series.map((s: any) => s.name);
  expect(names).toEqual(["Senior", "Mezzanine", "Revolver"]);
  expect(o.xAxis.data).toEqual(["Y1", "Y2"]);
  expect(o.series[0].data).toEqual([3000, 2200]);
});
