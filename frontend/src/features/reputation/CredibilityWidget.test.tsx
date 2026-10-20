import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { makeProfile } from "@/features/social/test-helpers";
import { CredibilityWidget, CredibilityWidgetView } from "./CredibilityWidget";
import { CREDIBILITY_HELP_HREF, NEW_SCORE_HINT } from "./CredibilityBadge";
import { makeSummary, makeTrend } from "./test-helpers";

const api = vi.hoisted(() => ({ fetchReputation: vi.fn() }));
vi.mock("./reputation-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./reputation-api")>()),
  ...api,
}));

beforeEach(() => vi.clearAllMocks());

const view = (overrides = {}) => (
  <CredibilityWidgetView
    score={68}
    verified={20}
    falseCount={3}
    trend={makeTrend(60, 68)}
    trendPhase="ready"
    {...overrides}
  />
);

describe("CredibilityWidgetView", () => {
  it("shows the ring with the score, the counts, the sparkline and the help link", () => {
    render(view());
    expect(screen.getByRole("heading", { name: "Credibility" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Credibility score 68 out of 100." })).toHaveTextContent(
      "68",
    );
    expect(screen.getByText("20 verified")).toBeInTheDocument();
    expect(screen.getByText("3 FALSE")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Credibility rose from 60 to 68 over the last 30 days." }),
    ).toBeInTheDocument();
    expect(screen.getByText("Last 30 days")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "How this is calculated" })).toHaveAttribute(
      "href",
      CREDIBILITY_HELP_HREF,
    );
  });

  it("says New with the hint and draws no sparkline while the score is hidden", () => {
    render(view({ score: null, trend: null, trendPhase: "idle" }));
    const ring = screen.getByRole("img", { name: `Credibility: New. ${NEW_SCORE_HINT}` });
    expect(ring).toHaveTextContent("New");
    expect(screen.getByText(NEW_SCORE_HINT)).toBeInTheDocument();
    expect(screen.queryByText("Last 30 days")).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /last 30 days/ })).not.toBeInTheDocument();
  });

  it("shows a placeholder while the trend loads, and nothing when it is hidden", () => {
    const { container, rerender } = render(view({ trend: null, trendPhase: "loading" }));
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(1);
    rerender(view({ trend: null, trendPhase: "hidden" }));
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(0);
    expect(screen.queryByText("Last 30 days")).not.toBeInTheDocument();
  });

  it("gives the sparkline a table of the 30 days", () => {
    render(view());
    const table = screen.getByRole("table", { name: "Credibility score, last 30 days" });
    expect(within(table).getAllByRole("row")).toHaveLength(31);
  });

  it("is neutral: the ring and the line are grey, only the two dots carry verdict colours", () => {
    const { container } = render(view());
    expect(container.querySelector("circle.stroke-on-surface-variant")).not.toBeNull();
    expect(container.querySelector("path")).toHaveAttribute("stroke", "currentColor");
    expect(container.querySelectorAll(".bg-primary")).toHaveLength(1);
    expect(container.querySelectorAll(".bg-error")).toHaveLength(1);
    expect(container.querySelector(".stroke-primary, .text-primary, .stroke-error")).toBeNull();
  });

  it("formats big counts with a separator", () => {
    render(view({ verified: 1420 }));
    expect(screen.getByText("1,420 verified")).toBeInTheDocument();
  });
});

describe("CredibilityWidget", () => {
  it("renders the ring and counts from the profile at once, and fetches only the trend", async () => {
    api.fetchReputation.mockResolvedValue(makeSummary());
    const profile = makeProfile({
      username: "bob",
      counts: { followers: 1, following: 1, posts: 30, verified: 20, false: 3 },
      reputation: { score: 68, sample: 23 },
    });
    render(<CredibilityWidget profile={profile} />);
    expect(screen.getByRole("img", { name: /^Credibility score 68/ })).toBeInTheDocument();
    expect(screen.getByText("20 verified")).toBeInTheDocument();
    await screen.findByText("Last 30 days");
    expect(api.fetchReputation).toHaveBeenCalledWith("bob", expect.any(AbortSignal));
  });

  it("makes no request for an account whose score is hidden", () => {
    render(<CredibilityWidget profile={makeProfile()} />);
    expect(screen.getByRole("img", { name: /^Credibility: New/ })).toHaveTextContent("New");
    expect(api.fetchReputation).not.toHaveBeenCalled();
  });

  it("keeps the ring and counts when the trend request fails", async () => {
    api.fetchReputation.mockRejectedValue(new Error("down"));
    render(<CredibilityWidget profile={makeProfile({ reputation: { score: 68, sample: 5 } })} />);
    await waitFor(() => expect(api.fetchReputation).toHaveBeenCalled());
    await waitFor(() => expect(document.querySelector(".animate-pulse")).toBeNull());
    expect(screen.getByRole("img", { name: /^Credibility score 68/ })).toBeInTheDocument();
    expect(screen.queryByText("Last 30 days")).not.toBeInTheDocument();
  });
});
