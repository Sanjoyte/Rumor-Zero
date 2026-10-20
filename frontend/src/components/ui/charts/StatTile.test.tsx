import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatTile } from "./StatTile";

describe("StatTile", () => {
  it("shows the label, the value and the sub-line", () => {
    render(<StatTile label="Confidence" value="95%" sub="+10 points" />);
    expect(screen.getByText("Confidence")).toBeInTheDocument();
    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("+10 points")).toBeInTheDocument();
  });

  it("has no sub-line without one, and is plain text rather than an image", () => {
    const { container } = render(<StatTile label="Time" value="2 s" />);
    expect(container.querySelectorAll("p")).toHaveLength(2);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
