import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CREDIBILITY_HELP_HREF, CredibilityBadge, NEW_SCORE_HINT } from "./CredibilityBadge";

const SHOWN = { score: 72, sample: 23 };
const NEW = { score: null, sample: 2 };

describe("CredibilityBadge in the profile header", () => {
  it("shows the score and links to how it is calculated", () => {
    render(<CredibilityBadge variant="header" reputation={SHOWN} />);
    expect(screen.getByText("Credibility 72")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "How this is calculated" });
    expect(link).toHaveAttribute("href", "/how-it-works#credibility");
    expect(CREDIBILITY_HELP_HREF).toBe("/how-it-works#credibility");
    expect(screen.queryByTitle(NEW_SCORE_HINT)).toBeNull();
  });

  it("says New below three counted events, and why, to sighted and screen-reader users", () => {
    const { container } = render(<CredibilityBadge variant="header" reputation={NEW} />);
    const label = screen.getByTitle(NEW_SCORE_HINT);
    expect(label).toHaveTextContent(/^Credibility: New/);
    expect(label).toHaveTextContent(NEW_SCORE_HINT);
    expect(container.querySelector(".sr-only")).toHaveTextContent(NEW_SCORE_HINT);
    expect(screen.getByRole("link", { name: "How this is calculated" })).toBeInTheDocument();
  });

  it("shows a score of 0 as a score, not as New", () => {
    render(<CredibilityBadge variant="header" reputation={{ score: 0, sample: 40 }} />);
    expect(screen.getByText("Credibility 0")).toBeInTheDocument();
  });
});

describe("CredibilityBadge in a user row", () => {
  it("shows the neutral chip and the verified count, with no link", () => {
    render(<CredibilityBadge variant="row" reputation={SHOWN} verified={1420} />);
    expect(screen.getByText("Credibility 72")).toBeInTheDocument();
    expect(screen.getByText("· 1,420 verified")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("says New with its reason in the title", () => {
    render(<CredibilityBadge variant="row" reputation={NEW} verified={0} />);
    expect(screen.getByText("Credibility: New")).toHaveAttribute("title", NEW_SCORE_HINT);
    expect(screen.getByText("· 0 verified")).toBeInTheDocument();
  });
});

describe("CredibilityBadge stays neutral (user decision 2026-10-13)", () => {
  it.each([
    ["header", <CredibilityBadge key="h" variant="header" reputation={SHOWN} />],
    ["row", <CredibilityBadge key="r" variant="row" reputation={SHOWN} verified={84} />],
    ["header, new", <CredibilityBadge key="hn" variant="header" reputation={NEW} />],
    ["row, new", <CredibilityBadge key="rn" variant="row" reputation={NEW} verified={0} />],
  ])("%s: no teal, no seal", (_, element) => {
    const { container } = render(element);
    const html = container.innerHTML;
    expect(html).not.toMatch(/\b(text|bg|border)-primary\b/);
    expect(container.querySelector(".material-symbols-outlined")).toBeNull();
    expect(html).toContain("text-on-surface-variant");
  });

  it("uses c3's neutral chip in rows", () => {
    render(<CredibilityBadge variant="row" reputation={SHOWN} verified={84} />);
    expect(screen.getByText("Credibility 72")).toHaveClass(
      "rounded-lg",
      "border-outline-variant/30",
      "bg-surface-container",
      "text-on-surface-variant",
      "font-label-badge",
      "text-label-badge",
    );
  });
});
