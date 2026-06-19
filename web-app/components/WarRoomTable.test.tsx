import { it, expect } from "vitest";
import { render } from "@testing-library/react";
import { WarRoomTable } from "@/components/WarRoomTable";
import type { Passer } from "@/lib/types";

const passers: Passer[] = [
  { ticker: "TANLA", name: "Tanla Platforms", irr: 0.22, moic: 2.7, degenerate: false,
    feasibility: 80, max_bid_premium_pct: 35,
    scenario_irrs: { bull: 0.31, base: 0.22, bear: 0.09 } },
  { ticker: "JUSTDIAL", name: "Just Dial", irr: 0.19, moic: 2.4, degenerate: false,
    feasibility: 72, max_bid_premium_pct: 28,
    scenario_irrs: { bull: 0.28, base: 0.19, bear: 0.07 } },
  { ticker: "NOSCEN", name: "No Scenarios Ltd", irr: 0.15, moic: 2.0, degenerate: false,
    feasibility: 60, max_bid_premium_pct: null,
    scenario_irrs: null },
];

it("renders BULL / BASE / BEAR column headers", () => {
  const { getByText } = render(<WarRoomTable passers={passers} />);
  getByText(/BULL/i); getByText(/BASE/i); getByText(/BEAR/i);
});

it("renders a row per passer", () => {
  const { getByText } = render(<WarRoomTable passers={passers} />);
  getByText("TANLA"); getByText("JUSTDIAL");
});

it("renders — for null scenario_irrs", () => {
  const { getAllByText } = render(<WarRoomTable passers={passers} />);
  // NOSCEN row should have em-dashes
  expect(getAllByText("—").length).toBeGreaterThan(0);
});

it("renders nothing when no passer has scenario_irrs", () => {
  const noScenPassers = passers.map(p => ({ ...p, scenario_irrs: null }));
  const { container } = render(<WarRoomTable passers={noScenPassers} />);
  expect(container.firstChild).toBeNull();
});

it("renders — for scenario_irrs with all-null IRRs (degenerate passer)", () => {
  const degeneratePassers = [
    { ...passers[0], scenario_irrs: { bull: null, base: null, bear: null } },
  ];
  const { getAllByText } = render(<WarRoomTable passers={degeneratePassers} />);
  // Three em-dashes: one per scenario column
  expect(getAllByText("—").length).toBeGreaterThanOrEqual(3);
});
