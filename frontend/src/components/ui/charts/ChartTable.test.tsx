import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChartTable } from "./ChartTable";

describe("ChartTable", () => {
  it("is a captioned table with column and row headers", () => {
    render(<ChartTable caption="Spread" columns={["Day", "Likes"]} rows={[["Oct 1", 3]]} />);
    const table = screen.getByRole("table", { name: "Spread" });
    expect(within(table).getByRole("columnheader", { name: "Likes" })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: "Oct 1" })).toBeInTheDocument();
    expect(within(table).getByRole("cell", { name: "3" })).toBeInTheDocument();
  });

  it("is visually hidden", () => {
    render(<ChartTable caption="Spread" columns={["Day"]} rows={[]} />);
    expect(screen.getByRole("table")).toHaveClass("sr-only");
  });
});
