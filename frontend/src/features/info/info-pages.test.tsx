import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HowItWorks } from "./HowItWorks";
import { PrivacyPage } from "./PrivacyPage";
import { TermsPage } from "./TermsPage";
import { SCORE_EVENTS } from "./numbers";

describe("HowItWorks", () => {
  it("renders the status table with all nine real badges", () => {
    render(<HowItWorks />);
    expect(screen.getByRole("heading", { level: 1, name: "How verification works" })).toBeVisible();
    const table = screen.getByRole("table", { name: "Post labels and what each one means" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(9);
    for (const label of [
      "OPINION",
      "CHECKING FACTS…",
      "VERIFIED 94%",
      "VERIFIED · REVIEWED",
      "FALSE 88%",
      "FALSE · REVIEWED",
      "UNDER REVIEW",
      "REMOVED",
      "EMERGENCY",
    ]) {
      expect(within(table).getByText(label)).toBeInTheDocument();
    }
  });

  it("never says debunked", () => {
    const { container } = render(<HowItWorks />);
    expect(container.textContent).not.toMatch(/debunk/i);
    expect(container.textContent).toContain("FALSE");
  });

  it("answers each question the part lists", () => {
    render(<HowItWorks />);
    for (const question of [
      "Why aren’t opinions checked?",
      "How does the check work?",
      "What happens when a post is reported?",
      "Can I appeal a FALSE label or a removal?",
      "What is an emergency post?",
      "Why does a repost keep the original’s label?",
    ]) {
      expect(screen.getByRole("heading", { level: 3, name: question })).toBeVisible();
    }
  });

  it("explains emergencies: the six rules, the pin, the cost and the block", () => {
    render(<HowItWorks />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("pinned at the top of the feeds for 24 hours");
    expect(text).toContain("at least 7 days old");
    expect(text).toContain("at least 40");
    expect(text).toContain("cannot post emergencies for 30 days");
    expect(text).toContain("lifts early if that FALSE label is overturned");
    expect(text).toContain("2 reports send it to a moderator");
    expect(text).toContain("checked before other posts");
  });

  it("has the #credibility anchor, marked for legal review", () => {
    const { container } = render(<HowItWorks />);
    const section = container.querySelector("#credibility");
    expect(section).not.toBeNull();
    expect(within(section as HTMLElement).getByText("Needs legal review")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "How your credibility score is calculated" }),
    ).toBeVisible();
  });

  it("lists every event of the ARCHITECTURE §4a table and the appeal path", () => {
    render(<HowItWorks />);
    const table = screen.getByRole("table", {
      name: "Every event that changes a credibility score",
    });
    for (const event of SCORE_EVENTS) {
      expect(within(table).getByText(event.kind)).toBeInTheDocument();
    }
    expect(SCORE_EVENTS.map((e) => e.kind)).toEqual([
      "fact_true",
      "fact_false",
      "emergency_false",
      "post_removed",
      "report_upheld",
      "repost_true",
      "repost_false",
      "repost_emergency_false",
      "repost_removed",
      "reversal",
    ]);
    expect(
      screen.getByText(/You can appeal a FALSE label and a removal once per post/),
    ).toBeVisible();
    expect(screen.getByText(/Others see “New” until 3 of your posts/)).toBeVisible();
  });
});

describe("Privacy and Terms", () => {
  it("both say they need legal review", () => {
    for (const [page, title] of [
      [<PrivacyPage key="p" />, "Privacy"],
      [<TermsPage key="t" />, "Terms"],
    ] as const) {
      const { unmount } = render(page);
      expect(screen.getByRole("heading", { level: 1, name: title })).toBeVisible();
      expect(screen.getByText("Needs legal review")).toBeVisible();
      unmount();
    }
  });

  it("Terms has sections on verification labels and the credibility score", () => {
    render(<TermsPage />);
    expect(screen.getByRole("heading", { name: "Verification labels" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Credibility score" })).toBeVisible();
    expect(screen.getByRole("link", { name: "How verification works" })).toHaveAttribute(
      "href",
      "/how-it-works#credibility",
    );
  });

  it("Privacy points to the settings for export and deletion", () => {
    render(<PrivacyPage />);
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
  });
});
