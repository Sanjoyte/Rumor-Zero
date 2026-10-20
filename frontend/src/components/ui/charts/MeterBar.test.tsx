import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MeterBar } from "./MeterBar";

const TABLE = { caption: "Confidence", rows: [["Confidence", "95%"]] as [string, string][] };

function setup(props: Partial<Parameters<typeof MeterBar>[0]> = {}) {
  return render(<MeterBar value={95} summary="95% confidence" table={TABLE} {...props} />);
}

describe("MeterBar", () => {
  it("is an image named by its summary, with the table beside it, not inside", () => {
    setup();
    const image = screen.getByRole("img", { name: "95% confidence" });
    const table = screen.getByRole("table", { name: "Confidence" });
    expect(image).not.toContainElement(table);
    expect(within(table).getByRole("cell", { name: "95%" })).toBeInTheDocument();
  });

  it("fills to the value", () => {
    const { container } = setup({ value: 60 });
    expect(container.querySelector('[style*="width: 60%"]')).not.toBeNull();
  });

  it.each([
    [-5, "0%"],
    [250, "100%"],
    [Number.NaN, "0%"],
  ])("clamps %s to %s", (value, width) => {
    const { container } = setup({ value });
    expect(container.querySelector(`[style*="width: ${width}"]`)).not.toBeNull();
  });

  it("draws the threshold tick and its caption only when given", () => {
    const { container } = setup({ threshold: 85, thresholdLabel: "Threshold 85%" });
    expect(container.querySelector('[style*="left: 85%"]')).not.toBeNull();
    expect(screen.getByText("Threshold 85%")).toBeInTheDocument();
    const plain = setup();
    expect(plain.container.querySelectorAll('[style*="left:"]')).toHaveLength(0);
  });

  it("keeps the caption inside the bar near the ends", () => {
    const { container } = setup({ threshold: 99, thresholdLabel: "T" });
    expect(container.querySelector('[style*="left: 88%"]')).not.toBeNull();
    expect(container.querySelector('[style*="left: 99%"]')).not.toBeNull(); // the tick itself
  });

  it.each([
    ["primary", "bg-primary"],
    ["error", "bg-error"],
    ["neutral", "bg-on-surface-variant"],
  ] as const)("the %s tone fills with %s", (tone, cls) => {
    const { container } = setup({ tone });
    expect(container.querySelector(`.${cls}`)).not.toBeNull();
  });

  it("has no animation", () => {
    const { container } = setup({ threshold: 85 });
    expect(container.innerHTML).not.toMatch(/animate-|transition/);
  });
});
