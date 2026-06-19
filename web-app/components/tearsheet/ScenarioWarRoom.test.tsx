import { it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ScenarioWarRoom } from "@/components/tearsheet/ScenarioWarRoom";
import type { ScenarioBlock } from "@/lib/types";

const fixture: ScenarioBlock = {
  bull: {
    assumptions: { revenue_growth: 0.16, ebitda_margin: 0.25, exit_multiple: 12 },
    financials:  { revenue: 820, ebitda: 205, fcf_for_debt: 155 },
    returns:     { irr: 0.31, moic: 3.9, exit_equity: 1820 },
  },
  base: {
    assumptions: { revenue_growth: 0.08, ebitda_margin: 0.20, exit_multiple: 10 },
    financials:  { revenue: 620, ebitda: 112, fcf_for_debt: 82 },
    returns:     { irr: 0.22, moic: 2.7, exit_equity: 980 },
  },
  bear: {
    assumptions: { revenue_growth: 0.03, ebitda_margin: 0.15, exit_multiple: 8 },
    financials:  { revenue: 480, ebitda: 58, fcf_for_debt: 31 },
    returns:     { irr: 0.09, moic: 1.5, exit_equity: 410 },
  },
};

it("renders BULL / BASE / BEAR column headers", () => {
  const { getByText } = render(<ScenarioWarRoom scenarios={fixture} />);
  getByText("BULL"); getByText("BASE"); getByText("BEAR");
});

it("renders assumption rows", () => {
  const { getByText } = render(<ScenarioWarRoom scenarios={fixture} />);
  getByText("Rev growth"); getByText("Margin"); getByText("Exit multiple");
});

it("renders returns rows", () => {
  const { getByText } = render(<ScenarioWarRoom scenarios={fixture} />);
  getByText("IRR"); getByText("MOIC"); getByText("Exit equity");
});

it("renders nothing when scenarios is null", () => {
  const { container } = render(<ScenarioWarRoom scenarios={null} />);
  expect(container.firstChild).toBeNull();
});

it("reads fcf_for_debt not fcf", () => {
  const { getByText } = render(<ScenarioWarRoom scenarios={fixture} />);
  getByText("FCF");  // displayed label; ensure render doesn't crash on fcf_for_debt key
});
