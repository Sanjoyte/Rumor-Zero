import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { FeedItem, Post } from "@/lib/api/types";
import { FeedList } from "./FeedList";
import {
  BO,
  feedEntry,
  makePost,
  renderWithSessionAndToast,
  repostEntry,
  unavailableEntry,
} from "./test-helpers";
import type { CursorFeed } from "./useCursorFeed";

const api = vi.hoisted(() => ({ unrepostPost: vi.fn() }));
vi.mock("@/features/social/social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/social/social-api")>()),
  ...api,
}));

beforeEach(() => {
  api.unrepostPost.mockReset();
  api.unrepostPost.mockResolvedValue(undefined);
});

const post = (id: string, overrides: Partial<Post> = {}) =>
  makePost({ id, content: `Content of ${id}`, is_mine: false, ...overrides });
const entry = feedEntry;

// The cards carry like buttons (Part 7), which need the session and the toast region.
const render = (ui: React.ReactElement) => renderWithSessionAndToast(ui, "verified");

function feedWith(overrides: Partial<CursorFeed<FeedItem>> = {}): CursorFeed<FeedItem> {
  return {
    items: [],
    phase: "ready",
    error: null,
    hasMore: false,
    loadingMore: false,
    moreError: null,
    loadMore: vi.fn(),
    retry: vi.fn(),
    prepend: vi.fn(),
    append: vi.fn(),
    remove: vi.fn(),
    ...overrides,
  };
}

describe("FeedList", () => {
  it.each(["idle", "loading"] as const)("shows skeleton cards while %s", (phase) => {
    const { container } = render(<FeedList feed={feedWith({ phase })} />);
    expect(container.querySelector("[aria-busy='true']")).toBeInTheDocument();
    expect(screen.getByText("Loading posts…")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows an error with Try again", async () => {
    const feed = feedWith({
      phase: "error",
      error: new ApiError({ status: 0, code: "network_error", detail: "offline" }),
    });
    render(<FeedList feed={feed} />);
    expect(screen.getByText("Couldn't load posts")).toBeInTheDocument();
    expect(screen.getByText(/Check your connection/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(feed.retry).toHaveBeenCalledTimes(1);
  });

  it("says the server is waking up on a 503", () => {
    const error = new ApiError({ status: 503, code: "backend_waking", detail: "waking" });
    render(<FeedList feed={feedWith({ phase: "error", error })} />);
    expect(screen.getByText(/server is waking up/)).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<FeedList feed={feedWith()} />);
    expect(screen.getByText("No posts yet")).toBeInTheDocument();
    expect(screen.queryByText("You're caught up.")).toBeNull();
  });

  it("renders a card for each post, in order", () => {
    const items = [entry(post("a")), entry(post("b")), entry(post("c"))];
    render(<FeedList feed={feedWith({ items })} />);
    const cards = screen.getAllByRole("article");
    expect(cards).toHaveLength(3);
    expect(cards[0]).toHaveTextContent("Content of a");
    expect(cards[2]).toHaveTextContent("Content of c");
  });

  it("never shows a credibility score on a card (Part 11B: profiles and user rows only)", () => {
    const items = [
      entry(post("a")),
      entry(post("f", { post_type: "fact", status: "verified_true", verdict_source: "pipeline" })),
    ];
    render(<FeedList feed={feedWith({ items })} />);
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(document.body.textContent).not.toMatch(/credibility/i);
  });

  it("renders a fact with its status and first source", () => {
    const fact = post("f", {
      post_type: "fact",
      status: "pending",
      sources: [
        { value: "10.1000/xyz", kind: "doi" },
        { value: "https://example.org/a", kind: "url" },
      ],
    });
    render(<FeedList feed={feedWith({ items: [entry(fact)] })} />);
    expect(screen.getByText("CHECKING FACTS…")).toBeInTheDocument();
    expect(screen.getByText("doi.org/10.1000/xyz")).toBeInTheDocument();
    expect(screen.getByText("+1 more")).toBeInTheDocument();
  });

  it("has a Load more button that loads, and 'You're caught up.' at the end", async () => {
    const feed = feedWith({ items: [entry(post("a"))], hasMore: true });
    const { rerender } = render(<FeedList feed={feed} />);
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    expect(feed.loadMore).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("You're caught up.")).toBeNull();
    rerender(<FeedList feed={{ ...feed, hasMore: false }} />);
    expect(screen.getByText("You're caught up.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Load more/ })).toBeNull();
  });

  it("shows Loading… on the button while a page is loading", () => {
    render(
      <FeedList feed={feedWith({ items: [entry(post("a"))], hasMore: true, loadingMore: true })} />,
    );
    expect(screen.getByRole("button", { name: /Loading…/ })).toBeDisabled();
  });

  it("keeps the list and shows an inline error when Load more failed", () => {
    const moreError = new ApiError({ status: 0, code: "network_error", detail: "offline" });
    render(<FeedList feed={feedWith({ items: [entry(post("a"))], hasMore: true, moreError })} />);
    expect(screen.getByText(/Couldn't load more posts/)).toBeInTheDocument();
    expect(screen.getByText(/Content of a/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Load more/ })).toBeInTheDocument();
  });

  describe("reposts (Part 7B)", () => {
    it("shows a repost as the original's card with 'Reposted by' above it", () => {
      render(<FeedList feed={feedWith({ items: [repostEntry(post("r")), entry(post("a"))] })} />);
      const [first, second] = screen.getAllByRole("article");
      expect(first).toHaveTextContent("Content of r");
      expect(first).toHaveTextContent("Reposted by");
      expect(within(first).getByRole("link", { name: "Bo" })).toHaveAttribute("href", "/u/bo");
      expect(second).not.toHaveTextContent("Reposted by");
    });

    it("gives a repost the original's own action bar, acting on the original", async () => {
      render(
        <FeedList
          feed={feedWith({ items: [repostEntry(post("r", { repost_count: 3, like_count: 2 }))] })}
        />,
      );
      expect(await screen.findByRole("button", { name: "Repost 3" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Like 2" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Content of r/ })).toHaveAttribute("href", "/p/r");
    });

    it("shows the original's live label on a repost", () => {
      const original = post("r", { post_type: "fact", status: "pending" });
      render(<FeedList feed={feedWith({ items: [repostEntry(original)] })} />);
      expect(screen.getByRole("article")).toHaveTextContent("CHECKING FACTS…");
    });

    it("lays a polled status over a repost's original", () => {
      const original = post("r", { post_type: "fact", status: "pending" });
      render(
        <FeedList
          feed={feedWith({ items: [repostEntry(original)] })}
          statusUpdates={{
            r: {
              id: "r",
              status: "verified_true",
              confidence_score: "94.00",
              verdict_source: "pipeline",
            },
          }}
        />,
      );
      expect(screen.getByRole("article")).toHaveTextContent("VERIFIED 94%");
    });

    it("shows 'This post is no longer available' for a repost of a deleted or removed post", () => {
      render(<FeedList feed={feedWith({ items: [unavailableEntry("x"), entry(post("a"))] })} />);
      const [first] = screen.getAllByRole("article");
      expect(first).toHaveTextContent("This post is no longer available");
      expect(first).toHaveTextContent("Reposted by");
      expect(within(first).queryByRole("button", { name: /Like|Repost \d|Bookmark/ })).toBeNull();
    });

    it("turns a repost into the unavailable card when the poll says its original was removed", () => {
      const original = post("r", { post_type: "fact", status: "pending" });
      render(
        <FeedList
          feed={feedWith({ items: [repostEntry(original)] })}
          statusUpdates={{
            r: { id: "r", status: "removed", confidence_score: null, verdict_source: null },
          }}
        />,
      );
      expect(screen.getByRole("article")).toHaveTextContent("This post is no longer available");
      expect(screen.queryByText(/Content of r/)).toBeNull();
    });

    it("turns a repost into the unavailable card when the poll says its original is gone", () => {
      render(
        <FeedList feed={feedWith({ items: [repostEntry(post("r"))] })} gone={new Set(["r"])} />,
      );
      expect(screen.getByRole("article")).toHaveTextContent("This post is no longer available");
    });

    it("hides a post that already showed higher up: later repeats are not shown", () => {
      const items = [repostEntry(post("a")), entry(post("b")), entry(post("a"))];
      render(<FeedList feed={feedWith({ items })} />);
      const cards = screen.getAllByRole("article");
      expect(cards).toHaveLength(2);
      expect(cards[0]).toHaveTextContent("Reposted by");
      expect(cards[1]).toHaveTextContent("Content of b");
    });

    it("shows a post once even when two people reposted it", () => {
      const cy = { ...BO, id: "u-9", username: "cy", display_name: "Cy" };
      render(
        <FeedList
          feed={feedWith({ items: [repostEntry(post("a"), BO), repostEntry(post("a"), cy)] })}
        />,
      );
      expect(screen.getAllByRole("article")).toHaveLength(1);
      expect(screen.getByRole("link", { name: "Bo" })).toBeInTheDocument();
    });

    describe("Undo repost", () => {
      const mine = { ...BO, id: "u-1" }; // the session's user (`ME`) is u-1

      it("is offered on your own repost of a missing post, and removes the item", async () => {
        const feed = feedWith({ items: [unavailableEntry("x", mine)] });
        render(<FeedList feed={feed} />);
        await userEvent.click(await screen.findByRole("button", { name: "Undo repost" }));
        expect(api.unrepostPost).toHaveBeenCalledWith("x");
        await waitFor(() => expect(feed.remove).toHaveBeenCalledWith("repost:u-1:x"));
        expect(await screen.findByText("Repost removed.")).toBeInTheDocument();
      });

      it("is not offered on someone else's repost", async () => {
        render(<FeedList feed={feedWith({ items: [unavailableEntry("x", BO)] })} />);
        await screen.findByText("This post is no longer available");
        expect(screen.queryByRole("button", { name: "Undo repost" })).toBeNull();
      });

      it("keeps the item and toasts when the request fails", async () => {
        api.unrepostPost.mockRejectedValue(new ApiError({ status: 500, code: "x", detail: "x" }));
        const feed = feedWith({ items: [unavailableEntry("x", mine)] });
        render(<FeedList feed={feed} />);
        await userEvent.click(await screen.findByRole("button", { name: "Undo repost" }));
        expect(
          await screen.findByText("Couldn't undo your repost. Try again."),
        ).toBeInTheDocument();
        expect(feed.remove).not.toHaveBeenCalled();
        expect(screen.getByRole("button", { name: "Undo repost" })).toBeEnabled();
      });
    });
  });

  describe("an empty page with more behind it", () => {
    it("offers Load more instead of the empty state", () => {
      const feed = feedWith({ items: [], hasMore: true });
      render(<FeedList feed={feed} empty={<p>Nothing here</p>} />);
      expect(screen.queryByText("Nothing here")).toBeNull();
      expect(screen.getByRole("button", { name: /Load more/ })).toBeInTheDocument();
    });

    it("shows the empty state when nothing more can load", () => {
      render(<FeedList feed={feedWith({ items: [] })} empty={<p>Nothing here</p>} />);
      expect(screen.getByText("Nothing here")).toBeInTheDocument();
    });

    it("counts posts hidden as repeats or gone: all hidden and no more = empty", () => {
      render(
        <FeedList
          feed={feedWith({ items: [entry(post("a"))] })}
          gone={new Set(["a"])}
          empty={<p>Nothing here</p>}
        />,
      );
      expect(screen.getByText("Nothing here")).toBeInTheDocument();
    });
  });

  describe("polled statuses (Part 5)", () => {
    const pendingFact = (id: string) =>
      post(id, { post_type: "fact", status: "pending", is_mine: false });

    it("lays a polled status over the card, with its confidence", () => {
      const items = [entry(pendingFact("a")), entry(pendingFact("b"))];
      render(
        <FeedList
          feed={feedWith({ items })}
          statusUpdates={{
            a: {
              id: "a",
              status: "verified_true",
              confidence_score: "94.00",
              verdict_source: "pipeline",
            },
          }}
        />,
      );
      const [first, second] = screen.getAllByRole("article");
      expect(first).toHaveTextContent("VERIFIED 94%");
      expect(first).not.toHaveTextContent("CHECKING FACTS…");
      expect(second).toHaveTextContent("CHECKING FACTS…");
    });

    it("turns a card whose post was removed into the tombstone", () => {
      render(
        <FeedList
          feed={feedWith({ items: [entry(pendingFact("a"))] })}
          statusUpdates={{
            a: { id: "a", status: "removed", confidence_score: null, verdict_source: null },
          }}
        />,
      );
      const card = screen.getByRole("article");
      expect(card).toHaveTextContent("Removed by a moderator");
      expect(card).not.toHaveTextContent("Content of a");
    });

    it("hides a post the poll found deleted", () => {
      const items = [entry(pendingFact("a")), entry(pendingFact("b"))];
      render(<FeedList feed={feedWith({ items })} gone={new Set(["a"])} />);
      const cards = screen.getAllByRole("article");
      expect(cards).toHaveLength(1);
      expect(cards[0]).toHaveTextContent("Content of b");
    });

    it("links every card to its page", () => {
      render(<FeedList feed={feedWith({ items: [entry(post("a"))] })} />);
      expect(screen.getByRole("link", { name: /Content of a/ })).toHaveAttribute("href", "/p/a");
    });
  });

  describe("report flag (Part 8)", () => {
    // Someone else's posts (the session's user is `u-1`, like `makePost`'s default author).
    const theirs = (id: string, overrides: Partial<Post> = {}) =>
      post(id, { author: BO, ...overrides });

    it("puts a flag on every card of someone else's post, and none on your own", async () => {
      render(
        <FeedList
          feed={feedWith({
            items: [entry(theirs("a")), entry(post("b", { is_mine: true })), entry(theirs("c"))],
          })}
        />,
      );
      await screen.findAllByRole("button", { name: "Report" });
      expect(screen.getAllByRole("button", { name: "Report" })).toHaveLength(2);
    });

    it("marks a post you reported, and gives every card its own flag", async () => {
      render(
        <FeedList
          feed={feedWith({
            items: [entry(theirs("a", { reported_by_me: true })), entry(theirs("b"))],
          })}
        />,
      );
      expect(await screen.findAllByRole("button", { name: "You reported this" })).toHaveLength(1);
      expect(screen.getAllByRole("button", { name: "Report" })).toHaveLength(1);
      // No dialog is built until a flag is clicked: a feed doesn't carry 20 of them.
      expect(document.querySelector("dialog")).toBeNull();
    });

    it("reports the original from a repost item", async () => {
      render(<FeedList feed={feedWith({ items: [repostEntry(theirs("r"))] })} />);
      await userEvent.click(await screen.findByRole("button", { name: "Report" }));
      expect(screen.getByRole("dialog", { name: "Report this post" })).toBeInTheDocument();
      expect(screen.getByText(/Content of r/, { selector: "p" })).toBeInTheDocument();
    });
  });

  it("shows the default empty state, or the one it is given", () => {
    const { rerender } = render(<FeedList feed={feedWith()} />);
    expect(screen.getByText("No posts yet")).toBeInTheDocument();
    expect(screen.getByText("Be the first to post something.")).toBeInTheDocument();
    rerender(<FeedList feed={feedWith()} empty={<p>Follow people first</p>} />);
    expect(screen.getByText("Follow people first")).toBeInTheDocument();
    expect(screen.queryByText("No posts yet")).toBeNull();
  });

  it("ignores a custom empty state while there are posts", () => {
    render(
      <FeedList
        feed={feedWith({ items: [entry(post("a"))] })}
        empty={<p>Follow people first</p>}
      />,
    );
    expect(screen.queryByText("Follow people first")).toBeNull();
    expect(screen.getByText(/Content of a/)).toBeInTheDocument();
  });
});

describe("FeedList action bars (Part 7)", () => {
  it("puts a like button and a comment link, with the real counts, on each post card", async () => {
    const items = [
      entry(post("a", { like_count: 3, comment_count: 7, liked_by_me: true })),
      entry(post("b")),
    ];
    render(<FeedList feed={feedWith({ items })} />);
    expect(await screen.findByRole("button", { name: "Like 3" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("link", { name: "Comments 7" })).toHaveAttribute(
      "href",
      "/p/a#comments",
    );
    expect(screen.getByRole("button", { name: "Like 0" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("link", { name: "Comments 0" })).toHaveAttribute(
      "href",
      "/p/b#comments",
    );
  });

  it("has no bar on a removed post's tombstone card", () => {
    const items = [entry(post("a", { status: "removed", like_count: 9 }))];
    render(<FeedList feed={feedWith({ items })} />);
    expect(screen.queryByRole("button", { name: /Like/ })).toBeNull();
    expect(screen.queryByRole("link", { name: /Comments/ })).toBeNull();
  });
});

describe("FeedList removed posts (Part 11)", () => {
  const removed = (id: string, overrides: Partial<Post> = {}) =>
    post(id, {
      status: "removed",
      post_type: "fact",
      content: "",
      sources: [],
      is_mine: false,
      ...overrides,
    });
  const mineRemoved = (id: string, overrides: Partial<Post> = {}) =>
    removed(id, {
      is_mine: true,
      can_appeal: true,
      content: "My removed claim",
      removal_reason: "Personal attack",
      ...overrides,
    });

  it("shows a removed post the way everyone else sees it: a tombstone, no action bar", () => {
    render(<FeedList feed={feedWith({ items: [entry(removed("p1"))] })} />);
    expect(screen.getByText("Removed by a moderator")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows the author their own removed post with the reason and the appeal button", async () => {
    render(<FeedList feed={feedWith({ items: [entry(mineRemoved("p1"))] })} />);
    expect(screen.getByText(/My removed claim/)).toBeInTheDocument();
    expect(screen.getByText(/Only you can see this text/)).toBeInTheDocument();
    expect(screen.getByText("Reason given: Personal attack")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Request another look" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Like|Repost|Report|Bookmark/ })).toBeNull();
  });

  it("shows the chip, not the button, for an author whose appeal is open", () => {
    const item = mineRemoved("p1", { can_appeal: false, appeal_status: "open" });
    render(<FeedList feed={feedWith({ items: [entry(item)] })} />);
    expect(screen.getByText("APPEAL PENDING")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request another look" })).toBeNull();
  });

  it("turns a polled removal of somebody else's post into the tombstone", () => {
    const live = post("p1", { status: "pending", post_type: "fact" });
    render(
      <FeedList
        feed={feedWith({ items: [entry(live)] })}
        statusUpdates={{
          p1: { id: "p1", status: "removed", confidence_score: null, verdict_source: null },
        }}
      />,
    );
    expect(screen.getByText("Removed by a moderator")).toBeInTheDocument();
    expect(screen.queryByText(/Content of p1/)).toBeNull();
  });

  it("turns a polled removal of your own post into your own removed card, without a button", () => {
    const live = post("p1", { status: "pending", post_type: "fact", is_mine: true });
    render(
      <FeedList
        feed={feedWith({ items: [entry(live)] })}
        statusUpdates={{
          p1: { id: "p1", status: "removed", confidence_score: null, verdict_source: null },
        }}
      />,
    );
    expect(screen.getByText(/Content of p1/)).toBeInTheDocument();
    expect(screen.getByText(/Only you can see this text/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request another look" })).toBeNull();
  });

  it("keeps the chip after a poll builds a new object for the card", async () => {
    const user = userEvent.setup();
    const appeals = await import("@/features/appeals/appeals-api");
    const spy = vi
      .spyOn(appeals, "appealPost")
      .mockResolvedValue(mineRemoved("p1", { can_appeal: false, appeal_status: "open" }));
    const item = mineRemoved("p1");
    const view = render(<FeedList feed={feedWith({ items: [entry(item)] })} />);
    await user.click(await screen.findByRole("button", { name: "Request another look" }));
    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("APPEAL PENDING")).toBeInTheDocument();
    // A status overlay that says nothing new still makes the card build its post again.
    view.rerender(
      <FeedList
        feed={feedWith({ items: [entry({ ...item })] })}
        statusUpdates={{
          p1: { id: "p1", status: "removed", confidence_score: null, verdict_source: null },
        }}
      />,
    );
    expect(screen.getByText("APPEAL PENDING")).toBeInTheDocument();
    spy.mockRestore();
  });

  it("still shows a repost of somebody else's removed post as 'no longer available'", () => {
    render(<FeedList feed={feedWith({ items: [unavailableEntry("gone")] })} />);
    expect(screen.getByText("This post is no longer available")).toBeInTheDocument();
  });
});
