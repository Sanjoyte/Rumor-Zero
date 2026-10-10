import { StrictMode } from "react";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithSessionAndToast, type SessionKind } from "@/features/posts/test-helpers";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { CommentSection } from "./CommentSection";
import { SOCIAL_MESSAGES } from "./messages";
import { makeComment } from "./test-helpers";

const api = vi.hoisted(() => ({
  fetchComments: vi.fn(),
  createComment: vi.fn(),
  deleteComment: vi.fn(),
}));
vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  ...api,
}));

const NOW = new Date("2026-10-08T12:00:00Z");
const page = (items: ReturnType<typeof makeComment>[], nextCursor: string | null = null) => ({
  items,
  nextCursor,
});

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchComments.mockResolvedValue(page([]));
  api.deleteComment.mockResolvedValue(undefined);
});

function renderSection(
  kind: SessionKind = "verified",
  { count = 0, onCountChange = vi.fn() } = {},
) {
  renderWithSessionAndToast(
    <CommentSection postId="p1" count={count} onCountChange={onCountChange} now={NOW} />,
    kind,
  );
  return onCountChange;
}

describe("CommentSection", () => {
  it("has the heading with the count, the label, the composer and the empty state", async () => {
    renderSection("verified", { count: 0 });
    expect(screen.getByRole("heading", { name: "Comments (0)" })).toBeInTheDocument();
    expect(screen.getByText("Oldest first")).toBeInTheDocument();
    expect(await screen.findByText("No comments yet")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Add a comment" })).toBeInTheDocument();
    expect(document.getElementById("comments")).toBe(
      screen.getByRole("region", { name: /Comments/ }),
    );
  });

  it("loads the post's comments, oldest first, once the session is known", async () => {
    api.fetchComments.mockResolvedValue(
      page([
        makeComment({ id: "a", content: "first" }),
        makeComment({ id: "b", content: "second" }),
      ]),
    );
    renderSection("verified", { count: 2 });
    expect(await screen.findByText("first")).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(api.fetchComments).toHaveBeenCalledWith("p1", null, expect.any(AbortSignal));
  });

  it("waits for the session before it asks for the comments", async () => {
    renderSection("loading");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(api.fetchComments).not.toHaveBeenCalled();
  });

  it("shows a visitor the comments and a way to log in, not a box", async () => {
    api.fetchComments.mockResolvedValue(page([makeComment({ content: "visible to all" })]));
    renderSection("anonymous", { count: 1 });
    expect(await screen.findByText("visible to all")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: SOCIAL_MESSAGES.logInToComment })).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("adds your comment at the end and raises the count by one", async () => {
    api.fetchComments.mockResolvedValue(page([makeComment({ id: "a", content: "older" })]));
    api.createComment.mockResolvedValue(
      makeComment({ id: "mine", content: "Newest", is_mine: true }),
    );
    const onCountChange = renderSection("verified", { count: 1 });
    await screen.findByText("older");
    await userEvent.type(screen.getByRole("textbox", { name: "Add a comment" }), "Newest");
    await userEvent.click(screen.getByRole("button", { name: "Comment" }));
    expect(await screen.findByText("Newest")).toBeInTheDocument();
    expect(onCountChange).toHaveBeenCalledWith(2);
    const order = screen.getAllByRole("article").map((a) => a.textContent ?? "");
    expect(order[0]).toContain("older");
    expect(order[1]).toContain("Newest");
    expect(await screen.findByText("Comment posted.")).toBeInTheDocument();
  });

  it("asks before it deletes, then removes the comment and lowers the count", async () => {
    api.fetchComments.mockResolvedValue(
      page([
        makeComment({ id: "a", content: "not mine" }),
        makeComment({ id: "b", content: "mine to delete", is_mine: true }),
      ]),
    );
    const onCountChange = renderSection("verified", { count: 2 });
    await screen.findByText("mine to delete");
    expect(screen.getAllByRole("button", { name: "Delete" })).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: "Delete this comment?" });
    expect(api.deleteComment).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete comment" }));
    await waitFor(() => expect(screen.queryByText("mine to delete")).toBeNull());
    expect(api.deleteComment).toHaveBeenCalledWith("b");
    expect(onCountChange).toHaveBeenCalledWith(1);
    expect(screen.getByText("not mine")).toBeInTheDocument();
    expect(await screen.findByText(SOCIAL_MESSAGES.commentDeleted)).toBeInTheDocument();
  });

  it("never lowers the count below zero", async () => {
    api.fetchComments.mockResolvedValue(page([makeComment({ id: "b", is_mine: true })]));
    const onCountChange = renderSection("verified", { count: 0 });
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await userEvent.click(await screen.findByRole("button", { name: "Delete comment" }));
    await waitFor(() => expect(onCountChange).toHaveBeenCalledWith(0));
  });

  it("loads more comments below the first page", async () => {
    api.fetchComments
      .mockResolvedValueOnce(page([makeComment({ id: "a", content: "page one" })], "c2"))
      .mockResolvedValueOnce(page([makeComment({ id: "b", content: "page two" })]));
    renderSection("verified", { count: 2 });
    await screen.findByText("page one");
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByText("page two")).toBeInTheDocument();
    expect(api.fetchComments).toHaveBeenLastCalledWith("p1", "c2", expect.any(AbortSignal));
    expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
  });

  it("shows an error and recovers with Try again", async () => {
    api.fetchComments
      .mockRejectedValueOnce(new ApiError({ status: 0, code: "network_error", detail: "off" }))
      .mockResolvedValueOnce(page([makeComment({ content: "back again" })]));
    renderSection();
    expect(await screen.findByText(SOCIAL_MESSAGES.commentsFailed)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("back again")).toBeInTheDocument();
  });

  it("still marks your own comments under StrictMode, which aborts and re-runs the first fetch", async () => {
    api.fetchComments.mockImplementation(
      (_id: string, _cursor: string | null, signal: AbortSignal) =>
        new Promise((resolve, reject) => {
          signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          setTimeout(() => resolve(page([makeComment({ content: "mine", is_mine: true })])), 0);
        }),
    );
    // Mounted after the session settled, as when you open the page from a card.
    function AfterSession() {
      const { status } = useAuth();
      return status === "authenticated" ? (
        <CommentSection postId="p1" count={1} onCountChange={vi.fn()} now={NOW} />
      ) : null;
    }
    renderWithSessionAndToast(
      <StrictMode>
        <AfterSession />
      </StrictMode>,
      "verified",
    );
    expect(await screen.findByRole("button", { name: "Delete" })).toBeInTheDocument();
  });
});
