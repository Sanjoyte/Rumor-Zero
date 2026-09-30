import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button, buttonClasses } from "./Button";

describe("Button", () => {
  it("defaults to a primary button of type button", () => {
    render(<Button>Create account</Button>);
    const button = screen.getByRole("button", { name: "Create account" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveClass("bg-secondary", "text-on-secondary", "shadow-sm", "rounded-lg");
  });

  it.each([
    ["secondary", "border-outline-variant"],
    ["ghost", "text-on-surface-variant"],
    ["destructive", "bg-error"],
  ] as const)("renders the %s variant", (variant, expected) => {
    render(<Button variant={variant}>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveClass(expected);
  });

  it("renders an icon button that keeps its accessible name", () => {
    render(
      <Button variant="icon" aria-label="Close">
        x
      </Button>,
    );
    expect(screen.getByRole("button", { name: "Close" })).toHaveClass("p-space-xs");
  });

  it("goes full width and 44px tall as a block button", () => {
    render(<Button block>Log in</Button>);
    expect(screen.getByRole("button")).toHaveClass("w-full", "h-11");
  });

  it("fires onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("ignores clicks and announces busy while loading", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Saving
      </Button>,
    );
    const button = screen.getByRole("button", { name: /Saving/ });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("gives links the same classes through buttonClasses", () => {
    expect(buttonClasses({ variant: "secondary", block: true })).toContain("w-full");
  });
});
