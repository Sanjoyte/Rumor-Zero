import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { badgeNumber, UnreadBadge, unreadHint } from "./UnreadBadge";

describe("UnreadBadge", () => {
  it("renders nothing for 0 or less", () => {
    const { container, rerender } = render(<UnreadBadge count={0} variant="pill" />);
    expect(container).toBeEmptyDOMElement();
    rerender(<UnreadBadge count={-2} variant="corner" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the number, hidden from assistive tech", () => {
    render(<UnreadBadge count={12} variant="pill" />);
    const badge = screen.getByTestId("unread-badge");
    expect(badge).toHaveTextContent("12");
    expect(badge).toHaveAttribute("aria-hidden", "true");
  });

  it("is a pill after the label or a corner on the icon", () => {
    const { rerender } = render(<UnreadBadge count={1} variant="pill" />);
    expect(screen.getByTestId("unread-badge").className).toContain("min-w-5");
    expect(screen.getByTestId("unread-badge").className).not.toContain("absolute");
    rerender(<UnreadBadge count={1} variant="corner" />);
    expect(screen.getByTestId("unread-badge").className).toContain("absolute");
  });

  it("swaps the colours when inverted", () => {
    const { rerender } = render(<UnreadBadge count={1} variant="pill" />);
    expect(screen.getByTestId("unread-badge")).toHaveClass("bg-secondary", "text-on-secondary");
    rerender(<UnreadBadge count={1} variant="pill" inverted />);
    expect(screen.getByTestId("unread-badge")).toHaveClass("bg-on-secondary", "text-secondary");
  });
});

describe("badgeNumber and unreadHint", () => {
  it("is exact up to 99 and 99+ above", () => {
    expect(badgeNumber(1)).toBe("1");
    expect(badgeNumber(99)).toBe("99");
    expect(badgeNumber(100)).toBe("99+");
  });

  it("speaks ', N unread' and nothing for 0", () => {
    expect(unreadHint(0)).toBe("");
    expect(unreadHint(5)).toBe(", 5 unread");
    expect(unreadHint(300)).toBe(", 99+ unread");
  });
});
