import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PasswordStrength } from "@/lib/password-strength";
import { PasswordStrengthMeter } from "./PasswordStrengthMeter";

function filledSegments(container: HTMLElement) {
  return container.querySelectorAll("[data-filled='true']").length;
}

describe("PasswordStrengthMeter", () => {
  it.each([
    [0, 0, ""],
    [1, 1, "Weak"],
    [2, 2, "Fair"],
    [3, 3, "Good"],
    [4, 4, "Strong"],
  ] as [PasswordStrength, number, string][])(
    "score %d fills %d segments and reads %j",
    (score, filled, label) => {
      const { container } = render(<PasswordStrengthMeter score={score} />);
      expect(filledSegments(container)).toBe(filled);
      expect(container.querySelectorAll("[data-filled]")).toHaveLength(4);
      if (label) expect(screen.getByText(label)).toBeInTheDocument();
    },
  );

  it("announces the level politely and hides the bar from assistive tech", () => {
    const { container } = render(<PasswordStrengthMeter score={3} />);
    expect(screen.getByText("Good")).toHaveAttribute("aria-live", "polite");
    expect(container.querySelector("[data-filled]")?.parentElement).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("goes red for Weak, amber for Fair and teal for Good and Strong", () => {
    const fill = (score: PasswordStrength) => {
      const { container, unmount } = render(<PasswordStrengthMeter score={score} />);
      const cls = container.querySelector("[data-filled='true']")?.className ?? "";
      unmount();
      return cls;
    };
    expect(fill(1)).toContain("bg-error");
    expect(fill(2)).toContain("bg-verdict-review");
    expect(fill(3)).toContain("bg-primary");
    expect(fill(4)).toContain("bg-primary");
  });
});
