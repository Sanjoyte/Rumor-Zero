import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sparkline } from "./Sparkline";

const TABLE = {
  caption: "Credibility, last 30 days",
  columns: ["Day", "Score"],
  rows: [
    ["Oct 1", 60],
    ["Oct 2", 62],
  ],
};

function setup(values: number[]) {
  return render(<Sparkline values={values} summary="Credibility rose" table={TABLE} />);
}

describe("Sparkline", () => {
  it("is an image named by its summary, with a sibling table of the days", () => {
    setup([60, 62]);
    const image = screen.getByRole("img", { name: "Credibility rose" });
    const table = screen.getByRole("table", { name: "Credibility, last 30 days" });
    expect(image).not.toContainElement(table);
    expect(screen.getByRole("rowheader", { name: "Oct 2" })).toBeInTheDocument();
  });

  it("draws a path in currentColor and a round end dot", () => {
    const { container } = setup([60, 62, 61]);
    expect(container.querySelector("path")).toHaveAttribute("stroke", "currentColor");
    expect(container.querySelector("path")?.getAttribute("d")).toMatch(/^M/);
    expect(container.querySelector("circle")).toHaveClass("fill-current");
  });

  it("has a uniform view box so the dot stays round", () => {
    const { container } = setup([60]);
    const box = container.querySelector("svg")!.getAttribute("viewBox")!.split(" ");
    expect(Number(box[2]) / Number(box[3])).toBeCloseTo(112 / 24);
    expect(container.querySelector("svg")).toHaveClass("h-6", "w-28");
  });

  it("draws nothing for no values", () => {
    const { container } = setup([]);
    expect(container.querySelector("path")).toBeNull();
    expect(container.querySelector("circle")).toBeNull();
  });

  it("has no animation", () => {
    const { container } = setup([60, 62]);
    expect(container.innerHTML).not.toMatch(/animate-|transition/);
  });
});
