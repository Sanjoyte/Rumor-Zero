import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AuthLayout } from "./AuthLayout";
import { MarketingFooter } from "./MarketingFooter";
import { MarketingNav } from "./MarketingNav";

let pathname = "/";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

function logoSize(container: HTMLElement) {
  const img = within(container).getByRole("img", { name: "Rumor Zero" });
  return {
    height: Number(img.getAttribute("height")),
    link: img.closest("a")?.getAttribute("href"),
  };
}

describe("AuthLayout", () => {
  it("frames the page in the form-width card with the large logo linking home", () => {
    render(
      <AuthLayout>
        <h1>Welcome back</h1>
      </AuthLayout>,
    );
    const main = screen.getByRole("main");
    expect(main).toHaveClass("max-w-form");
    expect(logoSize(main)).toEqual({ height: 48, link: "/" });
    expect(within(main).getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });
});

describe("MarketingNav", () => {
  it("has the logo, How it works, Log in and Sign up", () => {
    pathname = "/";
    render(<MarketingNav />);
    const header = screen.getByRole("banner");
    expect(logoSize(header)).toEqual({ height: 36, link: "/" });
    expect(screen.getByRole("link", { name: "How it works" })).toHaveAttribute(
      "href",
      "/how-it-works",
    );
    expect(screen.getByRole("link", { name: "How it works" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Sign up" })).toHaveAttribute("href", "/signup");
    expect(screen.queryByText(/About|Community Guidelines/)).toBeNull();
  });

  it("marks the current page", () => {
    pathname = "/how-it-works";
    render(<MarketingNav />);
    expect(screen.getByRole("link", { name: "How it works" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});

describe("MarketingFooter", () => {
  it("has the small logo, the three page links and the copyright line", () => {
    render(<MarketingFooter />);
    const footer = screen.getByRole("contentinfo");
    expect(logoSize(footer)).toEqual({ height: 24, link: "/" });
    const links = within(screen.getByRole("navigation", { name: "Footer" })).getAllByRole("link");
    expect(links.map((link) => [link.textContent, link.getAttribute("href")])).toEqual([
      ["How verification works", "/how-it-works"],
      ["Privacy", "/privacy"],
      ["Terms", "/terms"],
    ]);
    expect(within(footer).getByText("© 2026 Rumor Zero")).toBeInTheDocument();
    expect(within(footer).queryByText(/Inc\.|Network|Edition|Evidence-First/)).toBeNull();
  });
});
