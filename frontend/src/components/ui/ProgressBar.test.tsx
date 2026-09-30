import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProgressBar } from "./ProgressBar";

describe("ProgressBar", () => {
  it("is a named progressbar with its value", () => {
    render(<ProgressBar value={42} label="Credibility" />);
    const bar = screen.getByRole("progressbar", { name: "Credibility" });
    expect(bar).toHaveAttribute("aria-valuenow", "42");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect((bar.firstChild as HTMLElement).style.width).toBe("42%");
  });

  it("clamps out-of-range and invalid values", () => {
    const { rerender } = render(<ProgressBar value={150} label="Bar" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    rerender(<ProgressBar value={-5} label="Bar" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
    rerender(<ProgressBar value={Number.NaN} label="Bar" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
  });

  it("colours the fill by tone", () => {
    const { rerender } = render(<ProgressBar value={50} label="Bar" />);
    expect(screen.getByRole("progressbar").firstChild).toHaveClass("bg-primary");
    rerender(<ProgressBar value={50} label="Bar" tone="error" />);
    expect(screen.getByRole("progressbar").firstChild).toHaveClass("bg-error");
  });
});
