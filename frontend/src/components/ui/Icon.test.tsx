import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Icon } from "./Icon";

describe("Icon", () => {
  it("renders the glyph name and hides a decorative icon from assistive tech", () => {
    render(<Icon name="check_circle" />);
    const icon = screen.getByText("check_circle");
    expect(icon).toHaveClass("material-symbols-outlined", "text-[1rem]");
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });

  it("uses the requested size from the sanctioned scale", () => {
    render(<Icon name="bolt" size="sm" />);
    expect(screen.getByText("bolt")).toHaveClass("text-[0.875rem]");
  });

  it("fills the glyph when asked", () => {
    render(<Icon name="verified" filled />);
    expect(screen.getByText("verified")).toHaveClass("[font-variation-settings:'FILL'_1]");
  });

  it("becomes a named image when it has a label", () => {
    render(<Icon name="warning" label="Warning" />);
    expect(screen.getByRole("img", { name: "Warning" })).toBeInTheDocument();
  });
});
