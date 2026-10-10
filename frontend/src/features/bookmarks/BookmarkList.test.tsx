import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { feedEntry, makePost, renderWithSessionAndToast } from "@/features/posts/test-helpers";
import { BookmarkList } from "./BookmarkList";

const api = vi.hoisted(() => ({ fetchBookmarks: vi.fn() }));
vi.mock("@/features/social/social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/social/social-api")>()),
  ...api,
}));

const saved = (id: string, extra = {}) =>
  feedEntry(
    makePost({ id, content: `Saved ${id}`, is_mine: false, bookmarked_by_me: true, ...extra }),
  );

beforeEach(() => {
  api.fetchBookmarks.mockReset();
});

describe("BookmarkList", () => {
  it("shows the heading and the saved posts, each with its bookmark on", async () => {
    api.fetchBookmarks.mockResolvedValue({ items: [saved("a"), saved("b")], nextCursor: null });
    renderWithSessionAndToast(<BookmarkList />);
    expect(screen.getByRole("heading", { level: 1, name: "Bookmarks" })).toBeInTheDocument();
    expect(await screen.findByText(/Saved a/)).toBeInTheDocument();
    expect(screen.getByText(/Saved b/)).toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: "Bookmark" })) {
      expect(button).toHaveAttribute("aria-pressed", "true");
    }
    expect(api.fetchBookmarks).toHaveBeenCalledWith(null, expect.anything());
  });

  it("says nothing is saved, and that only you can see the list", async () => {
    api.fetchBookmarks.mockResolvedValue({ items: [], nextCursor: null });
    renderWithSessionAndToast(<BookmarkList />);
    expect(await screen.findByText("No bookmarks yet")).toBeInTheDocument();
    expect(
      screen.getByText("Posts you bookmark appear here. Only you can see them."),
    ).toBeInTheDocument();
  });

  it("shows skeletons while loading", () => {
    api.fetchBookmarks.mockReturnValue(new Promise(() => {}));
    renderWithSessionAndToast(<BookmarkList />);
    expect(screen.getByText("Loading posts…")).toBeInTheDocument();
  });

  it("loads the next page with the cursor, then says you're caught up", async () => {
    api.fetchBookmarks
      .mockResolvedValueOnce({ items: [saved("a")], nextCursor: "c2" })
      .mockResolvedValueOnce({ items: [saved("b")], nextCursor: null });
    renderWithSessionAndToast(<BookmarkList />);
    await userEvent.click(await screen.findByRole("button", { name: /Load more/ }));
    expect(await screen.findByText(/Saved b/)).toBeInTheDocument();
    expect(api.fetchBookmarks).toHaveBeenLastCalledWith("c2", expect.anything());
    expect(screen.getByText("You're caught up.")).toBeInTheDocument();
  });

  it("shows an error with Try again and recovers", async () => {
    api.fetchBookmarks
      .mockRejectedValueOnce(new ApiError({ status: 0, code: "network_error", detail: "off" }))
      .mockResolvedValueOnce({ items: [saved("a")], nextCursor: null });
    renderWithSessionAndToast(<BookmarkList />);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/Saved a/)).toBeInTheDocument();
  });

  it("asks nothing while the session is still being restored", async () => {
    api.fetchBookmarks.mockResolvedValue({ items: [saved("a")], nextCursor: null });
    renderWithSessionAndToast(<BookmarkList />, "loading");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(api.fetchBookmarks).not.toHaveBeenCalled();
  });

  it("fetches once the session settles, even under StrictMode's double effects", async () => {
    api.fetchBookmarks.mockResolvedValue({ items: [saved("a")], nextCursor: null });
    renderWithSessionAndToast(
      <StrictMode>
        <BookmarkList />
      </StrictMode>,
    );
    expect(await screen.findByText(/Saved a/)).toBeInTheDocument();
    await waitFor(() => expect(api.fetchBookmarks).toHaveBeenCalled());
  });

  it("polls a saved post that is still being checked", async () => {
    api.fetchBookmarks.mockResolvedValue({
      items: [saved("a", { post_type: "fact", status: "pending" })],
      nextCursor: null,
    });
    renderWithSessionAndToast(<BookmarkList />);
    expect(await screen.findByText("CHECKING FACTS…")).toBeInTheDocument();
  });
});
