import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { testSession } from "@/features/auth/test-helpers";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import DevUiPage from "./page";

/** As the root layout renders it: the Follow back button of a notification needs the session. */
function renderGallery() {
  return render(
    <AuthProvider session={testSession({}, { loggedIn: true }).session}>
      <ToastProvider>{DevUiPage()}</ToastProvider>
    </AuthProvider>,
  );
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("/dev/ui", () => {
  it("renders the gallery outside production", () => {
    vi.stubEnv("NODE_ENV", "development");
    renderGallery();
    expect(screen.getByRole("heading", { level: 1, name: "UI gallery" })).toBeInTheDocument();
    for (const name of [
      "Button",
      "TextField, PasswordField, Textarea",
      "Tabs, SegmentedControl, FilterChips",
      "StatusBadge, CategoryChip, VerdictStripe",
      "Stitch b1: PostCard",
      "Stitch b1: pinned emergencies",
      "Charts: MeterBar, StatTile, BarChart, RingGauge, Sparkline",
      "Stitch b3: How this was checked",
      "Stitch c1, b4 and c2: Credibility",
      "Stitch b4: search results",
      "Stitch c4: notifications",
      "Stitch b2 and d1: modals",
    ]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
  });

  it("shows every row of the badge table, worded FALSE", () => {
    vi.stubEnv("NODE_ENV", "development");
    renderGallery();
    const badges = document.getElementById("badges") as HTMLElement;
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
      expect(within(badges).getByText(label)).toBeInTheDocument();
    }
    expect(document.body.textContent).not.toMatch(/debunk/i);
  });

  it("shows the emergency card with its violet stripe in the Stitch b1 section", () => {
    vi.stubEnv("NODE_ENV", "development");
    renderGallery();
    const cards = document.getElementById("stitch-post-cards") as HTMLElement;
    expect(cards.querySelector("[data-tone='tertiary']")).not.toBeNull();
    expect(within(cards).getAllByText("EMERGENCY").length).toBeGreaterThan(0);
  });

  it("shows the pinned emergencies open and folded (Part 11C)", () => {
    vi.stubEnv("NODE_ENV", "development");
    renderGallery();
    const pinned = document.getElementById("stitch-pinned") as HTMLElement;
    const open = within(pinned).getByRole("region", { name: "Emergency posts" });
    expect(within(open).getAllByRole("article")).toHaveLength(2);
    expect(within(open).getByRole("button", { name: "Show all (3)" })).toBeInTheDocument();
    expect(
      within(pinned).getByRole("region", { name: "2 emergency posts pinned" }),
    ).toBeInTheDocument();
  });

  it("answers 404 in a production build", () => {
    vi.stubEnv("NODE_ENV", "production");
    let thrown: unknown;
    try {
      DevUiPage();
    } catch (error) {
      thrown = error;
    }
    expect(thrown).toBeDefined();
    expect(String((thrown as { digest?: string }).digest)).toContain("404");
  });

  it("shows the charts, each with a text alternative (Part 11D)", () => {
    vi.stubEnv("NODE_ENV", "development");
    renderGallery();
    const charts = document.getElementById("charts") as HTMLElement;
    expect(within(charts).getAllByRole("img").length).toBeGreaterThanOrEqual(10);
    expect(within(charts).getAllByRole("table").length).toBeGreaterThanOrEqual(10);
    const stats = document.getElementById("stitch-stats") as HTMLElement;
    expect(within(stats).getAllByRole("heading", { name: "How this was checked" })).toHaveLength(5);
    expect(within(stats).getByText("Reviewed by a moderator")).toBeInTheDocument();
    expect(within(stats).getByText("Below today's threshold of 97%")).toBeInTheDocument();
    const credibility = document.getElementById("stitch-credibility") as HTMLElement;
    expect(within(credibility).getAllByRole("heading", { name: "Credibility" })).toHaveLength(3);
    expect(within(credibility).getByText("Ask for another look")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/debunk/i);
  });

  it("shows the search specimens with the terms marked (Part 12)", () => {
    vi.stubEnv("NODE_ENV", "development");
    renderGallery();
    const search = document.getElementById("stitch-search") as HTMLElement;
    const marks = [...search.querySelectorAll("mark")].map((mark) => mark.textContent);
    expect(marks).toContain("capacity");
    expect(within(search).getByRole("search", { name: "Search results" })).toBeInTheDocument();
    expect(within(search).getByText("Search Rumor Zero")).toBeInTheDocument();
    expect(within(search).getByText(/No results for/)).toBeInTheDocument();
    expect(within(search).getByText(/going too fast/)).toBeInTheDocument();
  });

  it("shows all nine notification kinds, unread and read (Part 13)", () => {
    vi.stubEnv("NODE_ENV", "development");
    renderGallery();
    const section = document.getElementById("stitch-notifications") as HTMLElement;
    const kinds = within(section)
      .getAllByRole("article")
      .map((article) => article.getAttribute("data-type"));
    expect(new Set(kinds)).toEqual(
      new Set([
        "follow",
        "like",
        "comment",
        "repost",
        "verdict",
        "under_review",
        "removed",
        "emergency_demoted",
        "appeal_resolved",
      ]),
    );
    expect(within(section).getAllByText("Unread").length).toBeGreaterThan(0);
    expect(within(section).getByText("VERIFIED")).toBeInTheDocument();
    expect(within(section).getByText("FALSE")).toBeInTheDocument();
    expect(within(section).getByText(/The decision stands/)).toBeInTheDocument();
    expect(within(section).getByText(/The decision was overturned/)).toBeInTheDocument();
    expect(section.textContent).not.toMatch(/debunk/i);
  });
});
