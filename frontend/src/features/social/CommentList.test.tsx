import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { CursorFeed } from "@/features/posts/useCursorFeed";
import { ApiError } from "@/lib/api/client";
import type { Comment } from "@/lib/api/types";
import { CommentList } from "./CommentList";
import { SOCIAL_MESSAGES } from "./messages";
import { makeComment } from "./test-helpers";

function feedWith(overrides: Partial<CursorFeed<Comment>> = {}): CursorFeed<Comment> {
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

const NOW = new Date("2026-10-08T12:00:00Z");

describe("CommentList", () => {
  it.each(["idle", "loading"] as const)("shows skeletons while %s", (phase) => {
    const { container } = render(
      <CommentList feed={feedWith({ phase })} onDelete={vi.fn()} now={NOW} />,
    );
    expect(container.querySelector("[aria-busy='true']")).toBeInTheDocument();
    expect(screen.getByText("Loading comments…")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows an error with Try again", async () => {
    const feed = feedWith({
      phase: "error",
      error: new ApiError({ status: 0, code: "network_error", detail: "offline" }),
    });
    render(<CommentList feed={feed} onDelete={vi.fn()} />);
    expect(screen.getByText(SOCIAL_MESSAGES.commentsFailed)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(feed.retry).toHaveBeenCalledTimes(1);
  });

  it("says the server is waking up on a 503", () => {
    const error = new ApiError({ status: 503, code: "backend_waking", detail: "x" });
    render(<CommentList feed={feedWith({ phase: "error", error })} onDelete={vi.fn()} />);
    expect(screen.getByText(SOCIAL_MESSAGES.waking)).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<CommentList feed={feedWith()} onDelete={vi.fn()} />);
    expect(screen.getByText("No comments yet")).toBeInTheDocument();
    expect(screen.getByText("Start the discussion.")).toBeInTheDocument();
  });

  it("shows the comments in the order given, and passes Delete up", async () => {
    const onDelete = vi.fn();
    const items = [
      makeComment({ id: "a", content: "first" }),
      makeComment({ id: "b", content: "second", is_mine: true }),
    ];
    render(<CommentList feed={feedWith({ items })} onDelete={onDelete} now={NOW} />);
    expect(screen.getAllByRole("article").map((a) => a.textContent)).toEqual([
      expect.stringContaining("first"),
      expect.stringContaining("second"),
    ]);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledWith(items[1]);
  });

  it("has Load more only while there is more, and none at the end", async () => {
    const feed = feedWith({ items: [makeComment()], hasMore: true });
    const { rerender } = render(<CommentList feed={feed} onDelete={vi.fn()} now={NOW} />);
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(feed.loadMore).toHaveBeenCalledTimes(1);
    rerender(<CommentList feed={{ ...feed, hasMore: false }} onDelete={vi.fn()} now={NOW} />);
    expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
  });

  it("shows Loading… on the button while a page loads", () => {
    const feed = feedWith({ items: [makeComment()], hasMore: true, loadingMore: true });
    render(<CommentList feed={feed} onDelete={vi.fn()} now={NOW} />);
    expect(screen.getByRole("button", { name: "Loading…" })).toBeInTheDocument();
  });

  it("keeps the list and shows an inline error when Load more failed", () => {
    const feed = feedWith({
      items: [makeComment({ content: "still here" })],
      hasMore: true,
      moreError: new Error("boom"),
    });
    render(<CommentList feed={feed} onDelete={vi.fn()} now={NOW} />);
    expect(screen.getByText("still here")).toBeInTheDocument();
    expect(screen.getByText(/Couldn't load more comments/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load more" })).toBeInTheDocument();
  });
});
