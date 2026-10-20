import { StrictMode } from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PostStats, PostStatsView, marginOf, STATS_MESSAGES } from "./PostStats";
import { makeDaily, makePost, makeStats } from "./test-helpers";

const api = vi.hoisted(() => ({ fetchPostStats: vi.fn() }));
vi.mock("./posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./posts-api")>()),
  ...api,
}));

const fact = (overrides = {}) =>
  makePost({
    post_type: "fact",
    status: "verified_true",
    verdict_source: "pipeline",
    ...overrides,
  });

const pipeline = (overrides = {}) =>
  makeStats({
    confidence_score: "95.00",
    confidence_threshold: 85,
    verdict_source: "pipeline",
    seconds_to_verdict: 134,
    verdict_at: "2026-10-08T12:02:14Z",
    ...overrides,
  });

beforeEach(() => vi.clearAllMocks());

describe("marginOf", () => {
  it("rounds the confidence and subtracts the threshold", () => {
    expect(marginOf("94.60", 85)).toEqual({ confidence: 95, threshold: 85, margin: 10 });
    expect(marginOf("80.00", 85)?.margin).toBe(-5);
  });

  it("is null without both numbers", () => {
    expect(marginOf(null, 85)).toBeNull();
    expect(marginOf("90", null)).toBeNull();
    expect(marginOf("x", 85)).toBeNull();
  });
});

describe("PostStatsView", () => {
  it("shows the meter, the three tiles and the time for a pipeline TRUE", () => {
    const { container } = render(<PostStatsView post={fact()} stats={pipeline()} />);
    expect(screen.getByRole("heading", { name: STATS_MESSAGES.heading })).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Confidence 95%. The automatic label threshold is 85%." }),
    ).toBeInTheDocument();
    expect(screen.getByText("Auto-label threshold 85%")).toBeInTheDocument();
    expect(screen.getByText("Confidence", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("95%", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("Threshold and margin")).toBeInTheDocument();
    expect(screen.getByText("+10 points")).toBeInTheDocument();
    expect(screen.getByText("Time to verdict")).toBeInTheDocument();
    expect(screen.getByText("2 min 14 s")).toBeInTheDocument();
    expect(container.querySelector(".bg-primary")).not.toBeNull();
    expect(container.querySelector(".bg-error")).toBeNull();
  });

  it("uses the error tone for a pipeline FALSE", () => {
    const { container } = render(
      <PostStatsView post={fact({ status: "verified_false" })} stats={pipeline()} />,
    );
    expect(container.querySelector(".bg-error")).not.toBeNull();
    expect(container.querySelector(".bg-primary")).toBeNull();
  });

  it("says 'under 1 s' for a check that was instant", () => {
    render(<PostStatsView post={fact()} stats={pipeline({ seconds_to_verdict: 0 })} />);
    expect(screen.getByText("under 1 s")).toBeInTheDocument();
  });

  it("a confidence exactly at the threshold has a margin of zero points, not 'below'", () => {
    render(
      <PostStatsView
        post={fact()}
        stats={pipeline({ confidence_score: "85.00", confidence_threshold: 85 })}
      />,
    );
    expect(screen.getByText("+0 points")).toBeInTheDocument();
    expect(screen.queryByText(/Below today's threshold/)).not.toBeInTheDocument();
  });

  it("reports a raised threshold in words, not as a negative margin", () => {
    render(<PostStatsView post={fact()} stats={pipeline({ confidence_threshold: 97 })} />);
    expect(screen.getByText("Below today's threshold of 97%")).toBeInTheDocument();
    expect(screen.queryByText(/points$/, { selector: "p" })).not.toBeInTheDocument();
  });

  it("shows no meter and no percentage for a moderator's verdict", () => {
    const { container } = render(
      <PostStatsView
        post={fact({ verdict_source: "moderator" })}
        stats={makeStats({
          verdict_source: "moderator",
          seconds_to_verdict: 7200,
          verdict_at: "2026-10-08T14:00:00Z",
        })}
      />,
    );
    expect(screen.getByText(STATS_MESSAGES.moderator)).toBeInTheDocument();
    expect(screen.getByText("Time to decision")).toBeInTheDocument();
    expect(screen.getByText("2 h")).toBeInTheDocument();
    expect(screen.queryByText("Confidence", { selector: "p" })).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\d+%/);
    expect(screen.queryByText(/threshold/i)).not.toBeInTheDocument();
  });

  it("a moderator's verdict without a recorded time has no tile", () => {
    render(
      <PostStatsView
        post={fact({ verdict_source: "moderator" })}
        stats={makeStats({ verdict_source: "moderator" })}
      />,
    );
    expect(screen.queryByText("Time to decision")).not.toBeInTheDocument();
  });

  it("a pending fact shows a note and no meter", () => {
    render(
      <PostStatsView
        post={fact({ status: "pending", verdict_source: null })}
        stats={makeStats()}
      />,
    );
    expect(screen.getByText(STATS_MESSAGES.pending)).toBeInTheDocument();
    expect(screen.queryByText("Confidence")).not.toBeInTheDocument();
    expect(screen.queryByText("Auto-label threshold 85%")).not.toBeInTheDocument();
  });

  it("a fact under review shows a note and no meter, whatever the stats hold", () => {
    render(
      <PostStatsView
        post={fact({ status: "under_review", verdict_source: null })}
        stats={makeStats()}
      />,
    );
    expect(screen.getByText(STATS_MESSAGES.underReview)).toBeInTheDocument();
    expect(screen.queryByText("Time to verdict")).not.toBeInTheDocument();
  });

  it("waits for the numbers when the label changed before they arrived", () => {
    const { container } = render(<PostStatsView post={fact()} stats={makeStats()} />);
    expect(screen.queryByText("Time to verdict")).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /Confidence/ })).not.toBeInTheDocument();
    expect(container.querySelector("section > div")).toBeEmptyDOMElement();
  });

  it("always shows the spread chart, with its caption and the comments only in the table", () => {
    const daily = makeDaily();
    daily[0] = { ...daily[0], reposts: 2, likes: 3, comments: 7 };
    render(<PostStatsView post={fact()} stats={pipeline({ daily })} />);
    expect(screen.getByRole("heading", { name: STATS_MESSAGES.spreadHeading })).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "Reposts and likes per day for the first 14 days: 2 reposts and 3 likes in all.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(STATS_MESSAGES.spreadCaption, { selector: "p" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: STATS_MESSAGES.spreadCaption });
    expect(within(table).getByRole("columnheader", { name: "Comments" })).toBeInTheDocument();
    expect(screen.queryByText("No reposts or likes yet.")).not.toBeInTheDocument();
  });

  it("an empty post shows empty bars and says so, not an error", () => {
    render(<PostStatsView post={fact({ status: "pending" })} stats={makeStats()} />);
    expect(screen.getByText(STATS_MESSAGES.spreadEmpty)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("singular words for one repost and one like", () => {
    const daily = makeDaily();
    daily[1] = { ...daily[1], reposts: 1, likes: 1 };
    render(<PostStatsView post={fact()} stats={pipeline({ daily })} />);
    expect(
      screen.getByRole("img", { name: /: 1 repost and 1 like in all\.$/ }),
    ).toBeInTheDocument();
  });

  it("marks the verdict day when it is inside the 14 days, and not otherwise", () => {
    const inside = render(<PostStatsView post={fact()} stats={pipeline()} />);
    expect(inside.container.querySelectorAll(".mt-0\\.5.rounded-full")).toHaveLength(1);
    inside.unmount();
    const outside = render(
      <PostStatsView post={fact()} stats={pipeline({ verdict_at: "2026-12-01T00:00:00Z" })} />,
    );
    expect(outside.container.querySelectorAll(".mt-0\\.5.rounded-full")).toHaveLength(0);
    expect(screen.queryByText("Verdict")).not.toBeInTheDocument();
  });
});

describe("PostStats", () => {
  it("shows a placeholder while loading, then the section", async () => {
    let resolve: (value: unknown) => void = () => {};
    api.fetchPostStats.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<PostStats post={fact()} />);
    expect(screen.getByText("Loading how this was checked…")).toBeInTheDocument();
    resolve(pipeline());
    expect(
      await screen.findByRole("heading", { name: STATS_MESSAGES.heading }),
    ).toBeInTheDocument();
  });

  it("fetches this post's stats", async () => {
    api.fetchPostStats.mockResolvedValue(pipeline());
    render(<PostStats post={fact({ id: "p-9" })} />);
    await screen.findByRole("heading", { name: STATS_MESSAGES.heading });
    expect(api.fetchPostStats).toHaveBeenCalledWith("p-9", expect.any(AbortSignal));
  });

  it("hides the section when the request fails", async () => {
    api.fetchPostStats.mockRejectedValue(new Error("down"));
    const { container } = render(<PostStats post={fact()} />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("renders nothing for an opinion or a removed post", () => {
    api.fetchPostStats.mockResolvedValue(makeStats());
    const opinion = render(<PostStats post={makePost()} />);
    expect(opinion.container).toBeEmptyDOMElement();
    opinion.unmount();
    const removed = render(<PostStats post={fact({ status: "removed" })} />);
    expect(removed.container).toBeEmptyDOMElement();
  });

  it("fetches again when the label flips, and keeps the old numbers meanwhile", async () => {
    api.fetchPostStats.mockResolvedValueOnce(makeStats());
    const { rerender } = render(
      <PostStats post={fact({ status: "pending", verdict_source: null })} />,
    );
    expect(await screen.findByText(STATS_MESSAGES.pending)).toBeInTheDocument();
    let resolve: (value: unknown) => void = () => {};
    api.fetchPostStats.mockReturnValueOnce(new Promise((r) => (resolve = r)));
    rerender(<PostStats post={fact({ confidence_score: "95.00" })} />);
    expect(api.fetchPostStats).toHaveBeenCalledTimes(2);
    expect(screen.queryByText("Loading how this was checked…")).not.toBeInTheDocument();
    resolve(pipeline());
    expect(await screen.findByText("Time to verdict")).toBeInTheDocument();
  });

  it("keeps the numbers it has when a refetch fails", async () => {
    api.fetchPostStats.mockResolvedValueOnce(pipeline({ seconds_to_verdict: 7 }));
    const { rerender } = render(<PostStats post={fact()} />);
    expect(await screen.findByText("7 s")).toBeInTheDocument();
    api.fetchPostStats.mockRejectedValueOnce(new Error("down"));
    rerender(<PostStats post={fact({ confidence_score: "96.00" })} />);
    await waitFor(() => expect(api.fetchPostStats).toHaveBeenCalledTimes(2));
    await act(async () => {});
    expect(screen.getByText("7 s")).toBeInTheDocument();
  });

  it("does not fetch again when nothing about the label changed", async () => {
    api.fetchPostStats.mockResolvedValue(pipeline());
    const { rerender } = render(<PostStats post={fact()} />);
    await screen.findByRole("heading", { name: STATS_MESSAGES.heading });
    rerender(<PostStats post={fact({ like_count: 5 })} />);
    expect(api.fetchPostStats).toHaveBeenCalledTimes(1);
  });

  it("shows the section under StrictMode (effect, cleanup, effect)", async () => {
    api.fetchPostStats.mockResolvedValue(pipeline());
    render(
      <StrictMode>
        <PostStats post={fact()} />
      </StrictMode>,
    );
    expect(
      await screen.findByRole("heading", { name: STATS_MESSAGES.heading }),
    ).toBeInTheDocument();
  });

  it("ignores an answer that arrives after the post changed", async () => {
    let first: (value: unknown) => void = () => {};
    api.fetchPostStats.mockReturnValueOnce(new Promise((r) => (first = r)));
    api.fetchPostStats.mockResolvedValueOnce(pipeline({ seconds_to_verdict: 5 }));
    const { rerender } = render(
      <PostStats post={fact({ status: "pending", verdict_source: null })} />,
    );
    rerender(<PostStats post={fact()} />);
    expect(await screen.findByText("5 s")).toBeInTheDocument();
    await act(async () => first(makeStats()));
    expect(screen.getByText("5 s")).toBeInTheDocument();
  });
});
