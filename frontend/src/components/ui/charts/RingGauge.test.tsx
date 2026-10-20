import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RingGauge } from "./RingGauge";

const TABLE = { caption: "Credibility", rows: [["Score", "62"]] as [string, string][] };

function setup(value: number | null) {
  return render(
    <RingGauge
      value={value}
      centre={<span>{value ?? "New"}</span>}
      summary="Credibility 62"
      table={TABLE}
    />,
  );
}

const arc = (container: HTMLElement) => container.querySelector("circle[stroke-dasharray]");

describe("RingGauge", () => {
  it("is an image named by its summary, with the centre text and a sibling table", () => {
    setup(62);
    const image = screen.getByRole("img", { name: "Credibility 62" });
    expect(image).toHaveTextContent("62");
    expect(image).not.toContainElement(screen.getByRole("table", { name: "Credibility" }));
  });

  it("draws the arc to the value on a path of length 100", () => {
    const { container } = setup(62);
    expect(arc(container)).toHaveAttribute("stroke-dasharray", "62 100");
    expect(arc(container)).toHaveAttribute("pathLength", "100");
  });

  it("starts at 12 o'clock", () => {
    const { container } = setup(62);
    expect(container.querySelector("svg")).toHaveClass("-rotate-90");
  });

  it.each([null, 0, Number.NaN])("draws the track only for %s", (value) => {
    const { container } = setup(value);
    expect(arc(container)).toBeNull();
    expect(container.querySelectorAll("circle")).toHaveLength(1);
  });

  it("clamps above 100", () => {
    const { container } = setup(180);
    expect(arc(container)).toHaveAttribute("stroke-dasharray", "100 100");
  });

  it("is neutral grey and has no animation", () => {
    const { container } = setup(62);
    expect(arc(container)).toHaveClass("stroke-on-surface-variant");
    expect(container.innerHTML).not.toMatch(/animate-|transition/);
  });
});
