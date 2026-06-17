import { it, expect } from "vitest";
import { render } from "@testing-library/react";
import { StatementTable } from "@/components/tearsheet/StatementTable";

it("renders a header per year and a row per line item", () => {
  const rows = [{ year: 0, cash: 100, debt: 5000 }, { year: 1, cash: 120, debt: 4200 }];
  const { getByText, container } = render(
    <StatementTable title="Balance sheet" rows={rows as any}
      lines={[["cash", "Cash"], ["debt", "Debt"]]} startYear={0} />
  );
  getByText("Balance sheet"); getByText("Cash"); getByText("Y0"); getByText("Y1");
  expect(container.querySelectorAll("tbody tr").length).toBe(2);
});
