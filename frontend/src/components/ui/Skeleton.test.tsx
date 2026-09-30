import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("is a hidden, pulsing block that stops pulsing for reduced motion", () => {
    const { container } = render(<Skeleton className="h-4 w-32" />);
    expect(container.firstChild).toHaveAttribute("aria-hidden", "true");
    expect(container.firstChild).toHaveClass(
      "animate-pulse",
      "motion-reduce:animate-none",
      "bg-surface-container",
      "h-4",
      "w-32",
    );
  });
});
