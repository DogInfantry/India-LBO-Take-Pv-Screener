import { it, expect } from "vitest";
import { buildTornadoOption } from "@/lib/charts/tornado";

const t = {
  base_irr: 0.16,
  drivers: [
    { name: "Revenue growth", low: 0.14, high: 0.18 }, // swing 0.04
    { name: "EBITDA margin", low: 0.10, high: 0.22 },  // swing 0.12 (widest)
    { name: "Exit multiple", low: 0.13, high: 0.19 },  // swing 0.06
  ],
};

it("puts the widest swing at the top and splits downside/upside at base", () => {
  const o: any = buildTornadoOption(t);
  // top category (last in the array) = widest swing
  expect(o.yAxis.data[o.yAxis.data.length - 1]).toBe("EBITDA margin");

  const down = o.series.find((s: any) => s.name === "downside");
  const up = o.series.find((s: any) => s.name === "upside");
  const i = o.yAxis.data.length - 1; // EBITDA margin row
  expect(down.data[i]).toBeCloseTo(0.06); // base - low = 0.16 - 0.10
  expect(up.data[i]).toBeCloseTo(0.06);   // high - base = 0.22 - 0.16
});

it("drops drivers with a null end", () => {
  const o: any = buildTornadoOption({
    base_irr: 0.16,
    drivers: [{ name: "A", low: null, high: 0.2 }, { name: "B", low: 0.1, high: 0.2 }],
  });
  expect(o.yAxis.data).toEqual(["B"]);
});
