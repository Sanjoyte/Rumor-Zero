import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card } from "./Card";
import { VerdictStripe } from "./VerdictStripe";

describe("Card", () => {
  it("is a bordered white card with the single hairline elevation", () => {
    render(<Card data-testid="card">x</Card>);
    expect(screen.getByTestId("card")).toHaveClass(
      "bg-surface-container-lowest",
      "border-outline-variant/30",
      "rounded-lg",
      "shadow-sm",
      "relative",
    );
  });

  it("darkens its border on hover only when interactive", () => {
    const { rerender } = render(<Card data-testid="card">x</Card>);
    expect(screen.getByTestId("card")).not.toHaveClass("hover:border-outline/50");
    rerender(
      <Card data-testid="card" interactive>
        x
      </Card>,
    );
    expect(screen.getByTestId("card")).toHaveClass("hover:border-outline/50");
  });

  it("can render as an article", () => {
    render(<Card as="article">x</Card>);
    expect(screen.getByRole("article")).toBeInTheDocument();
  });
});

describe("VerdictStripe", () => {
  it.each([
    ["primary", "bg-primary"],
    ["error", "bg-error"],
    ["verdict-review", "bg-verdict-review"],
    ["tertiary", "bg-tertiary"],
    ["outline-variant", "bg-outline-variant"],
  ] as const)("paints the %s stripe", (tone, cls) => {
    const { container } = render(<VerdictStripe tone={tone} />);
    expect(container.firstChild).toHaveClass(cls, "w-1", "absolute", "left-0");
    expect(container.firstChild).toHaveAttribute("aria-hidden", "true");
  });
});
