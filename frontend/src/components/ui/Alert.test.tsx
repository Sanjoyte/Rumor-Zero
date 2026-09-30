import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Alert } from "./Alert";

describe("Alert", () => {
  it.each([
    ["info", "border-secondary/30", "info"],
    ["success", "border-primary/30", "check_circle"],
    ["warning", "border-verdict-review/30", "warning"],
    ["error", "border-error/30", "error"],
    ["neutral", "border-outline-variant/30", "shield"],
  ] as const)("renders the %s tone", (tone, border, glyph) => {
    const { container } = render(<Alert tone={tone}>Something happened</Alert>);
    expect(container.firstChild).toHaveClass(border, "rounded-lg");
    expect(screen.getByText(glyph)).toBeInTheDocument();
    expect(screen.getByText("Something happened")).toBeInTheDocument();
  });

  it("announces errors and successes, but leaves the rest silent", () => {
    const { rerender } = render(<Alert tone="error">Wrong password</Alert>);
    expect(screen.getByRole("alert")).toHaveTextContent("Wrong password");
    rerender(<Alert tone="success">Saved</Alert>);
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    rerender(<Alert tone="info">FYI</Alert>);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("shows a title above the text", () => {
    render(
      <Alert tone="warning" title="Verify your email">
        Check your inbox.
      </Alert>,
    );
    expect(screen.getByText("Verify your email")).toHaveClass("font-semibold");
  });

  it("only has a dismiss button when it can be dismissed", async () => {
    const onDismiss = vi.fn();
    const { rerender } = render(<Alert>Hello</Alert>);
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<Alert onDismiss={onDismiss}>Hello</Alert>);
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
