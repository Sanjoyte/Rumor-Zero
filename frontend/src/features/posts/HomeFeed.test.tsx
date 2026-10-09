import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { HomeFeed } from "./HomeFeed";
import {
  feedEntry,
  makePost,
  makeQuota,
  renderWithComposer,
  type SessionKind,
} from "./test-helpers";

const api = vi.hoisted(() => ({
  fetchStatuses: vi.fn(),
  createPost: vi.fn(),
  fetchFactQuota: vi.fn(),
  fetchRecentFeed: vi.fn(),
}));
vi.mock("./posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./posts-api")>()),
  ...api,
}));
const social = vi.hoisted(() => ({ fetchFollowingFeed: vi.fn() }));
vi.mock("@/features/social/social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/social/social-api")>()),
  ...social,
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/home",
}));

const page = (ids: string[], nextCursor: string | null = null) => ({
  items: ids.map((id) => feedEntry(makePost({ id, content: `Post ${id}`, is_mine: false }))),
  nextCursor,
});

beforeEach(() => {
  api.fetchStatuses.mockReset();
  api.fetchStatuses.mockResolvedValue([]);
  api.createPost.mockReset();
  api.fetchFactQuota.mockReset();
  api.fetchFactQuota.mockResolvedValue(makeQuota());
  api.fetchRecentFeed.mockReset();
  api.fetchRecentFeed.mockResolvedValue(page(["a", "b"]));
  social.fetchFollowingFeed.mockReset();
  social.fetchFollowingFeed.mockResolvedValue(page(["f1", "f2", "f3"]));
});

function renderHome(kind: SessionKind = "verified") {
  return renderWithComposer(<HomeFeed />, kind);
}

const cards = () => screen.queryAllByRole("article");
/** A card's claim, which is wrapped in curly quotes. */
const cardText = (id: string) => screen.getByText(new RegExp(`Post ${id}\u201D`));

describe("HomeFeed", () => {
  it("has a heading, a Recent tab and the composer trigger", async () => {
    renderHome();
    expect(screen.getByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Recent" })).toHaveAttribute("aria-selected", "true");
    expect(
      await screen.findByRole("button", { name: /What do you want to say/ }),
    ).toBeInTheDocument();
  });

  it("loads the Recent feed once the session is known", async () => {
    renderHome();
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(api.fetchRecentFeed).toHaveBeenCalledTimes(1);
    expect(api.fetchRecentFeed).toHaveBeenCalledWith(null, expect.any(AbortSignal));
  });

  it("doesn't fetch while the session is loading (it would go out without the token)", async () => {
    renderHome("loading");
    expect(screen.getByText("Loading posts…")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(api.fetchRecentFeed).not.toHaveBeenCalled();
  });

  it("shows the feed to visitors too", async () => {
    renderHome("anonymous");
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(screen.getByRole("link", { name: "Log in to post" })).toBeInTheDocument();
  });

  it("loads more with the cursor, and ends with 'You're caught up.'", async () => {
    api.fetchRecentFeed
      .mockResolvedValueOnce(page(["a", "b"], "cursor-1"))
      .mockResolvedValueOnce(page(["c"]));
    renderHome();
    await waitFor(() => expect(cards()).toHaveLength(2));
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    await waitFor(() => expect(cards()).toHaveLength(3));
    expect(api.fetchRecentFeed).toHaveBeenLastCalledWith("cursor-1", expect.any(AbortSignal));
    expect(screen.getByText("You're caught up.")).toBeInTheDocument();
  });

  it("shows an error with Try again when the feed can't load", async () => {
    api.fetchRecentFeed
      .mockRejectedValueOnce(new ApiError({ status: 0, code: "network_error", detail: "x" }))
      .mockResolvedValueOnce(page(["a"]));
    renderHome();
    expect(await screen.findByText("Couldn't load posts")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(cards()).toHaveLength(1));
  });

  it("puts a post made in the composer at the top, without reloading the feed", async () => {
    const created = makePost({ id: "mine", content: "Brand new post", is_mine: true });
    api.createPost.mockResolvedValue(created);
    renderHome();
    await waitFor(() => expect(cards()).toHaveLength(2));
    await userEvent.click(screen.getByRole("button", { name: /What do you want to say/ }));
    await userEvent.click(screen.getByRole("radio", { name: "Opinion" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Post text" }), "Brand new post");
    await userEvent.click(screen.getByRole("button", { name: "Post opinion" }));
    await waitFor(() => expect(cards()).toHaveLength(3));
    expect(within(cards()[0]).getByText(/Brand new post/)).toBeInTheDocument();
    expect(api.fetchRecentFeed).toHaveBeenCalledTimes(1);
  });

  it("shows a new fact as CHECKING FACTS… with its first source", async () => {
    api.createPost.mockResolvedValue(
      makePost({
        id: "fact-1",
        content: "A new claim",
        post_type: "fact",
        status: "pending",
        sources: [
          { value: "10.1000/xyz", kind: "doi" },
          { value: "https://example.org/report", kind: "url" },
        ],
      }),
    );
    renderHome();
    await waitFor(() => expect(cards()).toHaveLength(2));
    await userEvent.click(screen.getByRole("button", { name: /What do you want to say/ }));
    await userEvent.click(screen.getByRole("radio", { name: "Fact" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Post text" }), "A new claim");
    await userEvent.click(screen.getByRole("button", { name: "Post fact, will be checked" }));
    await waitFor(() => expect(cards()).toHaveLength(3));
    const card = cards()[0];
    expect(within(card).getByText("CHECKING FACTS…")).toBeInTheDocument();
    expect(within(card).getByText("doi.org/10.1000/xyz")).toBeInTheDocument();
    expect(within(card).getByText("+1 more")).toBeInTheDocument();
  });

  it("doesn't repeat a post the server's page already has", async () => {
    const created = makePost({ id: "a", content: "Post a", is_mine: true });
    api.createPost.mockResolvedValue(created);
    renderHome();
    await waitFor(() => expect(cards()).toHaveLength(2));
    await userEvent.click(screen.getByRole("button", { name: /What do you want to say/ }));
    await userEvent.click(screen.getByRole("radio", { name: "Opinion" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Post text" }), "x");
    await userEvent.click(screen.getByRole("button", { name: "Post opinion" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(cards()).toHaveLength(2);
  });

  describe("live badges (Part 5)", () => {
    const pendingPage = () => ({
      items: [
        feedEntry(
          makePost({
            id: "f1",
            content: "A pending claim",
            post_type: "fact",
            status: "pending",
            is_mine: false,
          }),
        ),
        feedEntry(makePost({ id: "o1", content: "An opinion", is_mine: false })),
      ],
      nextCursor: null,
    });

    it("updates a pending card's badge without a reload", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      try {
        api.fetchRecentFeed.mockResolvedValue(pendingPage());
        api.fetchStatuses.mockResolvedValue([
          {
            id: "f1",
            status: "verified_false",
            confidence_score: "88.00",
            verdict_source: "pipeline",
          },
        ]);
        renderHome();
        await waitFor(() => expect(cards()).toHaveLength(2));
        expect(screen.getByText("CHECKING FACTS…")).toBeInTheDocument();
        await act(() => vi.advanceTimersByTimeAsync(10_000));
        // Only the pending post is asked about, never the opinion.
        expect(api.fetchStatuses).toHaveBeenCalledWith(["f1"], expect.any(AbortSignal));
        expect(await screen.findByText("FALSE 88%")).toBeInTheDocument();
        expect(screen.queryByText("CHECKING FACTS…")).toBeNull();
        expect(api.fetchRecentFeed).toHaveBeenCalledTimes(1); // no refetch of the feed
      } finally {
        vi.useRealTimers();
      }
    });

    it("hides a post the poll no longer finds", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      try {
        api.fetchRecentFeed.mockResolvedValue(pendingPage());
        api.fetchStatuses.mockResolvedValue([]);
        renderHome();
        await waitFor(() => expect(cards()).toHaveLength(2));
        await act(() => vi.advanceTimersByTimeAsync(10_000));
        await waitFor(() => expect(cards()).toHaveLength(1));
        expect(screen.queryByText("A pending claim")).toBeNull();
      } finally {
        vi.useRealTimers();
      }
    });

    it("starts polling a fact you just posted", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      try {
        api.createPost.mockResolvedValue(
          makePost({ id: "new1", content: "Fresh fact", post_type: "fact", status: "pending" }),
        );
        api.fetchStatuses.mockResolvedValue([
          {
            id: "new1",
            status: "verified_true",
            confidence_score: "90.00",
            verdict_source: "pipeline",
          },
        ]);
        renderHome();
        await waitFor(() => expect(cards()).toHaveLength(2));
        await userEvent.click(screen.getByRole("button", { name: /What do you want to say/ }));
        await userEvent.click(screen.getByRole("radio", { name: "Fact" }));
        await userEvent.type(screen.getByRole("textbox", { name: "Post text" }), "Fresh fact");
        await userEvent.click(screen.getByRole("button", { name: "Post fact, will be checked" }));
        await waitFor(() => expect(cards()).toHaveLength(3));
        expect(api.fetchStatuses).not.toHaveBeenCalled();
        await act(() => vi.advanceTimersByTimeAsync(10_000));
        expect(api.fetchStatuses).toHaveBeenCalledWith(["new1"], expect.any(AbortSignal));
        expect(await screen.findByText("VERIFIED 90%")).toBeInTheDocument();
      } finally {
        vi.useRealTimers();
      }
    });

    it("asks nothing when no card is pending", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      try {
        renderHome();
        await waitFor(() => expect(cards()).toHaveLength(2));
        await act(() => vi.advanceTimersByTimeAsync(5 * 60_000));
        expect(api.fetchStatuses).not.toHaveBeenCalled();
      } finally {
        vi.useRealTimers();
      }
    });
  });
});

describe("HomeFeed: the Following tab (Part 6)", () => {
  const tabNames = () => screen.getAllByRole("tab").map((tab) => tab.textContent);

  it("is a second tab, after Recent, which stays selected", async () => {
    renderHome("verified");
    expect(await screen.findByRole("tab", { name: "Following" })).toBeInTheDocument();
    expect(tabNames()).toEqual(["Recent", "Following"]);
    expect(screen.getByRole("tab", { name: "Recent" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Following" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("is there for an unverified user too (reading needs only a login)", async () => {
    renderHome("unverified");
    expect(await screen.findByRole("tab", { name: "Following" })).toBeInTheDocument();
  });

  it("is not offered to a visitor, who never triggers its request", async () => {
    renderHome("anonymous");
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(tabNames()).toEqual(["Recent"]);
    expect(social.fetchFollowingFeed).not.toHaveBeenCalled();
  });

  it("makes no Following request until the tab is opened", async () => {
    renderHome("verified");
    await waitFor(() => expect(cards()).toHaveLength(2));
    await screen.findByRole("tab", { name: "Following" });
    expect(social.fetchFollowingFeed).not.toHaveBeenCalled();
  });

  it("loads the Following feed on first use, and keeps it when you switch back and forth", async () => {
    renderHome("verified");
    await userEvent.click(await screen.findByRole("tab", { name: "Following" }));
    expect(screen.getByRole("tab", { name: "Following" })).toHaveAttribute("aria-selected", "true");
    await waitFor(() => expect(cardText("f1")).toBeVisible());
    expect(social.fetchFollowingFeed).toHaveBeenCalledTimes(1);
    expect(social.fetchFollowingFeed).toHaveBeenCalledWith(null, expect.any(AbortSignal));
    await userEvent.click(screen.getByRole("tab", { name: "Recent" }));
    expect(cardText("a")).toBeVisible();
    await userEvent.click(screen.getByRole("tab", { name: "Following" }));
    expect(cardText("f1")).toBeVisible();
    expect(social.fetchFollowingFeed).toHaveBeenCalledTimes(1);
    expect(api.fetchRecentFeed).toHaveBeenCalledTimes(1);
  });

  it("loads more of the Following feed with its own cursor", async () => {
    social.fetchFollowingFeed
      .mockResolvedValueOnce(page(["f1"], "fc-1"))
      .mockResolvedValueOnce(page(["f2"]));
    renderHome("verified");
    await userEvent.click(await screen.findByRole("tab", { name: "Following" }));
    await waitFor(() => expect(cardText("f1")).toBeVisible());
    const panel = screen.getByRole("tabpanel", { name: "Following" });
    await userEvent.click(within(panel).getByRole("button", { name: /Load more/ }));
    await waitFor(() => expect(cardText("f2")).toBeVisible());
    expect(social.fetchFollowingFeed).toHaveBeenLastCalledWith("fc-1", expect.any(AbortSignal));
  });

  it("explains an empty Following feed and sends you to Recent", async () => {
    social.fetchFollowingFeed.mockResolvedValue(page([]));
    renderHome("verified");
    await userEvent.click(await screen.findByRole("tab", { name: "Following" }));
    expect(await screen.findByText("Follow people to see their posts here")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "See Recent" }));
    expect(screen.getByRole("tab", { name: "Recent" })).toHaveAttribute("aria-selected", "true");
    expect(cardText("a")).toBeVisible();
  });

  it("shows an error with Try again", async () => {
    social.fetchFollowingFeed
      .mockRejectedValueOnce(new ApiError({ status: 0, code: "network_error", detail: "x" }))
      .mockResolvedValueOnce(page(["f1"]));
    renderHome("verified");
    await userEvent.click(await screen.findByRole("tab", { name: "Following" }));
    const panel = screen.getByRole("tabpanel", { name: "Following" });
    expect(await within(panel).findByText("Couldn't load posts")).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(cardText("f1")).toBeVisible());
  });

  it("puts a new post at the top of Recent and of Following, without refetching either", async () => {
    api.createPost.mockResolvedValue(
      makePost({ id: "mine", content: "Brand new post", is_mine: true }),
    );
    renderHome("verified");
    await userEvent.click(await screen.findByRole("tab", { name: "Following" }));
    await waitFor(() => expect(cardText("f1")).toBeVisible());
    await userEvent.click(screen.getByRole("button", { name: /What do you want to say/ }));
    await userEvent.click(screen.getByRole("radio", { name: "Opinion" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Post text" }), "Brand new post");
    await userEvent.click(screen.getByRole("button", { name: "Post opinion" }));
    const following = screen.getByRole("tabpanel", { name: "Following" });
    await waitFor(() => expect(within(following).getAllByRole("article")).toHaveLength(4));
    expect(
      within(within(following).getAllByRole("article")[0]).getByText(/Brand new post/),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Recent" }));
    const recent = screen.getByRole("tabpanel", { name: "Recent" });
    expect(
      within(within(recent).getAllByRole("article")[0]).getByText(/Brand new post/),
    ).toBeInTheDocument();
    expect(social.fetchFollowingFeed).toHaveBeenCalledTimes(1);
    expect(api.fetchRecentFeed).toHaveBeenCalledTimes(1);
  });

  describe("badges", () => {
    beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
    afterEach(() => vi.useRealTimers());

    it("polls the pending posts of the tab you are looking at", async () => {
      api.fetchRecentFeed.mockResolvedValue({
        items: [
          feedEntry(
            makePost({ id: "r-pending", status: "pending", post_type: "fact", is_mine: false }),
          ),
        ],
        nextCursor: null,
      });
      social.fetchFollowingFeed.mockResolvedValue({
        items: [
          feedEntry(
            makePost({ id: "f-pending", status: "pending", post_type: "fact", is_mine: false }),
          ),
        ],
        nextCursor: null,
      });
      renderHome("verified");
      await waitFor(() => expect(cards()).toHaveLength(1));
      await act(() => vi.advanceTimersByTimeAsync(10_000));
      expect(api.fetchStatuses).toHaveBeenLastCalledWith(["r-pending"], expect.any(AbortSignal));
      await userEvent.click(await screen.findByRole("tab", { name: "Following" }));
      await waitFor(() => expect(social.fetchFollowingFeed).toHaveBeenCalled());
      await act(() => vi.advanceTimersByTimeAsync(15_000));
      await waitFor(() =>
        expect(api.fetchStatuses).toHaveBeenLastCalledWith(["f-pending"], expect.any(AbortSignal)),
      );
    });
  });
});
