import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { FeedItem, Post } from "@/lib/api/types";
import { FeedList } from "./FeedList";
import { feedEntry, makePost } from "./test-helpers";
import type { CursorFeed } from "./useCursorFeed";

const post = (id: string, overrides: Partial<Post> = {}) =>
  makePost({ id, content: `Content of ${id}`, is_mine: false, ...overrides });
const entry = feedEntry;

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

  it("leaves reposts out (Part 7B)", () => {
    const repost: FeedItem = {
      kind: "repost",
      post: post("r"),
      reposted_by: { id: "u2", username: "bo", display_name: "Bo", avatar_url: null },
      activity_at: "2026-10-08T12:00:00Z",
    };
    render(<FeedList feed={feedWith({ items: [repost, entry(post("a"))] })} />);
    expect(screen.getAllByRole("article")).toHaveLength(1);
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
