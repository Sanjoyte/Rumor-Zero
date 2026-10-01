import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import assets from "@/lib/brand-assets.json";
import { Logo, type LogoSize } from "./Logo";

const HEIGHTS: [LogoSize, number][] = [
  ["sm", 24],
  ["md", 36],
  ["lg", 48],
];

describe("Logo", () => {
  it('is the wordmark at medium size by default, named "Rumor Zero"', () => {
    render(<Logo />);
    const img = screen.getByRole("img", { name: "Rumor Zero" });
    expect(img.tagName).toBe("IMG");
    expect(img).toHaveAttribute("src", "/brand/logo.svg");
    expect(img).toHaveAttribute("height", "36");
  });

  it.each(HEIGHTS)(
    "wordmark %s is %i px tall with its width from the artwork ratio",
    (size, height) => {
      render(<Logo size={size} />);
      const img = screen.getByRole("img", { name: "Rumor Zero" });
      expect(img).toHaveAttribute("height", String(height));
      const expectedWidth = Math.round((height * assets.wordmark.width) / assets.wordmark.height);
      expect(img).toHaveAttribute("width", String(expectedWidth));
      expect(expectedWidth).toBeGreaterThan(height * 3);
    },
  );

  it.each(HEIGHTS)("mark %s is a %i px square", (size, height) => {
    render(<Logo variant="mark" size={size} />);
    const img = screen.getByRole("img", { name: "Rumor Zero" });
    expect(img).toHaveAttribute("src", "/brand/mark.svg");
    expect(img).toHaveAttribute("width", String(height));
    expect(img).toHaveAttribute("height", String(height));
  });

  it("has an empty alt text when decorative, so the name is not announced twice", () => {
    const { container } = render(
      <p>
        <Logo decorative /> Rumor Zero
      </p>,
    );
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("alt", "");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("always sets width and height, so there is no layout shift", () => {
    for (const variant of ["wordmark", "mark"] as const) {
      for (const [size] of HEIGHTS) {
        const { container, unmount } = render(<Logo variant={variant} size={size} />);
        const img = container.querySelector("img")!;
        expect(Number(img.getAttribute("width"))).toBeGreaterThan(0);
        expect(Number(img.getAttribute("height"))).toBeGreaterThan(0);
        unmount();
      }
    }
  });

  it("is a plain img, never inlined SVG, and passes a class through", () => {
    const { container } = render(<Logo className="mx-auto" />);
    expect(container.querySelector("svg")).toBeNull();
    expect(container.querySelector("img")).toHaveClass("mx-auto");
  });
});
