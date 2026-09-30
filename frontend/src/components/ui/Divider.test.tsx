import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Divider } from "./Divider";

describe("Divider", () => {
  it("is a plain hairline without a label", () => {
    const { container } = render(<Divider />);
    expect(container.querySelector("hr")).toHaveClass("border-t", "border-outline-variant/30");
  });

  it("centres a label on the hairline", () => {
    render(<Divider label="or continue with email" />);
    expect(screen.getByRole("separator", { name: "or continue with email" })).toBeInTheDocument();
    expect(screen.getByText("or continue with email")).toHaveClass("bg-surface-container-lowest");
  });
});
