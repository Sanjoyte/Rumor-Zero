import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PostCardSkeleton } from "./PostCardSkeleton";

describe("PostCardSkeleton", () => {
  it("is decorative: hidden from assistive tech, with no text", () => {
    const { container } = render(<PostCardSkeleton />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
    expect(container).toHaveTextContent("");
  });
});
