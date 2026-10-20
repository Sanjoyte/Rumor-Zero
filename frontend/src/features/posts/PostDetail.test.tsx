import { StrictMode } from "react";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { DETAIL_MESSAGES, PostDetail } from "./PostDetail";
import { BO, makePost, makeStats, renderWithComposer, type SessionKind } from "./test-helpers";

const api = vi.hoisted(() => ({
  fetchPost: vi.fn(),
  deletePost: vi.fn(),
  fetchStatuses: vi.fn(),
  fetchRecentFeed: vi.fn(),
  fetchFactQuota: vi.fn(),
  fetchPostStats: vi.fn(),
}));
vi.mock("./posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./posts-api")>()),
  ...api,
}));
const reports = vi.hoisted(() => ({ reportPost: vi.fn() }));
vi.mock("@/features/reports/reports-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/reports/reports-api")>()),
  ...reports,
}));
const social = vi.hoisted(() => ({
  fetchComments: vi.fn(),
  likePost: vi.fn(),
  unlikePost: vi.fn(),
  createComment: vi.fn(),
  deleteComment: vi.fn(),
}));
vi.mock("@/features/social/social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/social/social-api")>()),
  ...social,
}));
const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/p/x" }));

const ID = "11111111-1111-4111-8111-111111111111";
const fact = (overrides = {}) =>
  makePost({
    id: ID,
    post_type: "fact",
    status: "pending",
    content: "Solar capacity grew 30% last year.",
    is_mine: false,
    sources: [
      { value: "10.1038/s41558-024-02102", kind: "doi" },
      { value: "https://www.iea.org/reports/renewables-2023", kind: "url" },
    ],
    ...overrides,
  });

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchFactQuota.mockResolvedValue({
    limit: 10,
    used: 0,
    remaining: 10,
    window_hours: 24,
    next_slot_at: null,
  });
  api.fetchStatuses.mockResolvedValue([]);
  api.fetchPostStats.mockResolvedValue(makeStats());
  social.fetchComments.mockResolvedValue({ items: [], nextCursor: null });
  social.likePost.mockResolvedValue({ liked: true });
  social.unlikePost.mockResolvedValue(undefined);
});

function renderDetail(initial: ReturnType<typeof fact> | null, kind: SessionKind = "anonymous") {
  return renderWithComposer(<PostDetail id={ID} initial={initial} />, kind);
}

describe("PostDetail (server-rendered start)", () => {
  it("shows the claim, badges, author, date and verdict from the server's post, with no request", async () => {
    renderDetail(fact());
    expect(
      screen.getByRole("heading", { level: 1, name: /Solar capacity grew 30% last year\./ }),
    ).toBeInTheDocument();
    expect(screen.getByText("FACT")).toBeInTheDocument();
    expect(screen.getAllByText("CHECKING FACTS…").length).toBeGreaterThan(0);
    expect(screen.getByText("Ada")).toBeInTheDocument();
    expect(screen.getByText("@ada")).toBeInTheDocument();
    expect(screen.getByText("Oct 8, 2026, 12:00 PM UTC")).toHaveAttribute(
      "datetime",
      "2026-10-08T12:00:00Z",
    );
    expect(screen.getByRole("heading", { name: "Verdict" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sources (2)" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("link", { name: "Back to Home" })).toBeVisible());
    // An anonymous visitor already has the whole anonymous view: nothing to fetch.
    expect(api.fetchPost).not.toHaveBeenCalled();
  });

  it("sets an opinion in italic with no verdict block and no sources", () => {
    renderDetail(makePost({ id: ID, content: "Rain is nice", is_mine: false }));
    const claim = screen.getByRole("heading", { level: 1 });
    expect(claim).toHaveClass("italic");
    expect(screen.getByText("OPINION")).toBeInTheDocument();
    expect(screen.getByText("Opinions aren't fact-checked.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Verdict" })).toBeNull();
    expect(screen.queryByRole("heading", { name: /Sources/ })).toBeNull();
  });

  it("sets a fact in upright claim type", () => {
    renderDetail(fact());
    const claim = screen.getByRole("heading", { level: 1 });
    expect(claim).toHaveClass("font-claim-headline");
    expect(claim).not.toHaveClass("italic");
  });

  it("shows a pipeline verdict with its percentage and explanation", () => {
    renderDetail(
      fact({ status: "verified_true", verdict_source: "pipeline", confidence_score: "94.00" }),
    );
    expect(screen.getByText("VERIFIED 94%")).toBeInTheDocument();
    expect(screen.getByText("Checked automatically · 94% confidence")).toBeInTheDocument();
  });

  it("shows a moderator's verdict and note, and an emergency chip while it is pinned", () => {
    // A verified emergency stays pinned until it expires (§4b); a FALSE one never is (below).
    renderDetail(
      fact({
        status: "verified_true",
        verdict_source: "moderator",
        verdict_note: "The report says so.",
        is_emergency: true,
        emergency_active: true,
      }),
    );
    expect(screen.getByText("VERIFIED · REVIEWED")).toBeInTheDocument();
    expect(screen.getByText("Reviewed by a moderator")).toBeInTheDocument();
    expect(screen.getByText(/The report says so\./)).toBeInTheDocument();
    expect(screen.getByText("EMERGENCY")).toBeInTheDocument();
  });

  it("never shows the emergency chip on a FALSE post, even if the flag says active", () => {
    // A FALSE always ends the priority; a polled FALSE arrives before the refetch.
    renderDetail(
      fact({
        status: "verified_false",
        verdict_source: "moderator",
        is_emergency: true,
        emergency_active: true,
      }),
    );
    expect(screen.getByText("FALSE · REVIEWED")).toBeInTheDocument();
    expect(screen.queryByText("EMERGENCY")).toBeNull();
  });

  it("links back home and offers Copy link, but not Delete, to a reader", () => {
    renderDetail(fact());
    expect(screen.getByRole("link", { name: "Back to Home" })).toHaveAttribute("href", "/home");
    expect(screen.getByRole("button", { name: "Copy link" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  });

  it("shows a blank display name as @username once", () => {
    renderDetail(fact({ author: { ...fact().author, display_name: "" } }));
    expect(screen.getAllByText("@ada")).toHaveLength(1);
  });
});

describe("PostDetail (the removed tombstone)", () => {
  const tombstone = (overrides = {}) =>
    fact({
      status: "removed",
      content: "",
      sources: [],
      verdict_note: "",
      confidence_score: null,
      verdict_source: null,
      ...overrides,
    });

  it("shows the public only a notice and the author row, no claim, badges or sources", () => {
    renderDetail(tombstone());
    expect(screen.getByText(DETAIL_MESSAGES.removed)).toBeInTheDocument();
    expect(screen.getByText("Ada")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(screen.queryByRole("heading", { name: /Verdict|Sources/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy link" })).toBeNull();
  });

  it("shows the author their own text, marked as removed, once the signed-in fetch lands", async () => {
    api.fetchPost.mockResolvedValue(
      fact({ status: "removed", is_mine: true, content: "My removed claim" }),
    );
    renderDetail(tombstone(), "verified");
    expect(
      await screen.findByRole("heading", { level: 1, name: /My removed claim/ }),
    ).toBeVisible();
    expect(screen.getByText(/Only you can see this text/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });
});

describe("PostDetail (fetching)", () => {
  it("still gets the signed-in view under StrictMode, which aborts and re-runs the first fetch", async () => {
    api.fetchPost.mockImplementation(
      (_id: string, signal: AbortSignal) =>
        new Promise((resolve, reject) => {
          signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          setTimeout(() => resolve(fact({ is_mine: true })), 0);
        }),
    );
    // Mounted after the session settled, as when you click a card: the effect then runs with a
    // known user, so StrictMode's abort-and-rerun hits a real request.
    function AfterSession() {
      const { status } = useAuth();
      return status === "authenticated" ? <PostDetail id={ID} initial={fact()} /> : null;
    }
    renderWithComposer(
      <StrictMode>
        <AfterSession />
      </StrictMode>,
      "verified",
    );
    expect(await screen.findByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("fetches once for a signed-in visitor, to get the personal parts", async () => {
    api.fetchPost.mockResolvedValue(fact({ is_mine: true }));
    renderDetail(fact(), "verified");
    expect(await screen.findByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(api.fetchPost).toHaveBeenCalledTimes(1);
    expect(api.fetchPost).toHaveBeenCalledWith(ID, expect.any(AbortSignal));
  });

  it("waits for the session to be known before fetching", async () => {
    renderDetail(null, "loading");
    expect(screen.getByText("Loading post…")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(api.fetchPost).not.toHaveBeenCalled();
  });

  it("fetches by itself when the server couldn't read the post", async () => {
    api.fetchPost.mockResolvedValue(fact());
    renderDetail(null);
    expect(screen.getByText("Loading post…")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1 })).toBeVisible();
    expect(api.fetchPost).toHaveBeenCalledTimes(1);
  });

  it("shows 'Post not found' for a 404", async () => {
    api.fetchPost.mockRejectedValue(new ApiError({ status: 404, code: "not_found", detail: "" }));
    renderDetail(null);
    expect(await screen.findByText("Post not found")).toBeInTheDocument();
    expect(screen.getByText(DETAIL_MESSAGES.notFound)).toBeInTheDocument();
  });

  it("shows an error with Try again for anything else, and recovers", async () => {
    const user = userEvent.setup();
    api.fetchPost.mockRejectedValueOnce(
      new ApiError({ status: 0, code: "network_error", detail: "" }),
    );
    renderDetail(null);
    expect(await screen.findByText(DETAIL_MESSAGES.loadFailed)).toBeInTheDocument();
    api.fetchPost.mockResolvedValue(fact());
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { level: 1 })).toBeVisible();
  });

  it("keeps the server's post, quietly, when the signed-in refresh fails", async () => {
    api.fetchPost.mockRejectedValue(
      new ApiError({ status: 503, code: "backend_waking", detail: "" }),
    );
    renderDetail(fact(), "verified");
    await waitFor(() => expect(api.fetchPost).toHaveBeenCalled());
    expect(screen.getByRole("heading", { level: 1 })).toBeVisible();
    expect(screen.queryByText(DETAIL_MESSAGES.loadFailed)).toBeNull();
  });

  it("shows 'Post not found' when a signed-in refresh finds it deleted", async () => {
    api.fetchPost.mockRejectedValue(new ApiError({ status: 404, code: "not_found", detail: "" }));
    renderDetail(fact(), "verified");
    expect(await screen.findByText("Post not found")).toBeInTheDocument();
  });
});

describe("PostDetail (deleting)", () => {
  const mine = () => fact({ is_mine: true });

  async function openModal() {
    const user = userEvent.setup();
    api.fetchPost.mockResolvedValue(mine());
    renderDetail(mine(), "verified");
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    return user;
  }

  it("asks first, then deletes, toasts and goes home", async () => {
    api.deletePost.mockResolvedValue(undefined);
    const user = await openModal();
    const dialog = await screen.findByRole("dialog", { name: "Delete this post?" });
    expect(api.deletePost).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Delete post" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/home"));
    expect(api.deletePost).toHaveBeenCalledWith(ID);
    expect(await screen.findByText(DETAIL_MESSAGES.deleted)).toBeInTheDocument();
  });

  it("stays put when the request fails", async () => {
    api.deletePost.mockRejectedValue(
      new ApiError({ status: 0, code: "network_error", detail: "" }),
    );
    const user = await openModal();
    const dialog = await screen.findByRole("dialog", { name: "Delete this post?" });
    await user.click(within(dialog).getByRole("button", { name: "Delete post" }));
    expect(await within(dialog).findByRole("alert")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("PostDetail (polling)", () => {
  it("watches a pending post and updates the badge without a reload", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      api.fetchStatuses.mockResolvedValue([
        { id: ID, status: "verified_true", confidence_score: "94.00", verdict_source: "pipeline" },
      ]);
      api.fetchPost.mockResolvedValue(
        fact({ status: "verified_true", verdict_source: "pipeline", confidence_score: "94.00" }),
      );
      renderDetail(fact());
      expect(screen.getAllByText("CHECKING FACTS…").length).toBeGreaterThan(0);
      await act(() => vi.advanceTimersByTimeAsync(10_000));
      expect(api.fetchStatuses).toHaveBeenCalledWith([ID], expect.any(AbortSignal));
      expect(await screen.findByText("VERIFIED 94%")).toBeInTheDocument();
      expect(screen.queryByText("CHECKING FACTS…")).toBeNull();
      // One quiet refetch brings the rest (a moderator's note, say).
      await waitFor(() => expect(api.fetchPost).toHaveBeenCalledTimes(1));
    } finally {
      vi.useRealTimers();
    }
  });

  it("doesn't poll a post that isn't pending", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderDetail(fact({ status: "verified_true", verdict_source: "pipeline" }));
      await act(() => vi.advanceTimersByTimeAsync(5 * 60_000));
      expect(api.fetchStatuses).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("turns a polled removal into the tombstone for a reader", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      api.fetchStatuses.mockResolvedValue([
        { id: ID, status: "removed", confidence_score: null, verdict_source: null },
      ]);
      api.fetchPost.mockResolvedValue(
        fact({ status: "removed", content: "", sources: [], is_mine: false }),
      );
      renderDetail(fact());
      await act(() => vi.advanceTimersByTimeAsync(10_000));
      expect(await screen.findByText(DETAIL_MESSAGES.removed)).toBeInTheDocument();
      expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("PostDetail author link (Part 6)", () => {
  it("links the author row to the profile", () => {
    renderDetail(fact());
    const link = screen.getByRole("link", { name: /Ada/ });
    expect(link).toHaveAttribute("href", "/u/ada");
    expect(link).toHaveTextContent("Oct 8, 2026, 12:00 PM UTC");
  });

  it("links the author on a removed post's tombstone too (the author is public)", () => {
    renderDetail(fact({ status: "removed", content: "", sources: [] }));
    expect(screen.getByRole("link", { name: /Ada/ })).toHaveAttribute("href", "/u/ada");
  });
});

describe("PostDetail likes and comments (Part 7)", () => {
  const comment = (overrides = {}) => ({
    id: "c-1",
    author: { id: "u-3", username: "cy", display_name: "Cy Lane", avatar_url: null },
    content: "A fair point.",
    is_mine: false,
    created_at: "2026-10-08T11:00:00Z",
    ...overrides,
  });

  it("shows the like button and comment link in the action row, and the discussion below the sources", async () => {
    social.fetchComments.mockResolvedValue({ items: [comment()], nextCursor: null });
    renderDetail(fact({ like_count: 4, comment_count: 1 }), "anonymous");
    expect(screen.getByRole("link", { name: "Like 4" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Comments 1" })).toHaveAttribute("href", "#comments");
    expect(screen.getByRole("heading", { name: "Comments (1)" })).toBeInTheDocument();
    expect(await screen.findByText("A fair point.")).toBeInTheDocument();
    const sources = screen.getByRole("heading", { name: "Sources (2)" });
    const comments = screen.getByRole("heading", { name: "Comments (1)" });
    expect(
      sources.compareDocumentPosition(comments) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("likes from the page, and the heading and button follow", async () => {
    api.fetchPost.mockResolvedValue(fact({ is_mine: false, like_count: 4 }));
    renderDetail(fact({ like_count: 4 }), "verified");
    await userEvent.click(await screen.findByRole("button", { name: "Like 4" }));
    expect(social.likePost).toHaveBeenCalledWith(ID);
    expect(await screen.findByRole("button", { name: "Like 5" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("takes the signed-in view's liked state when the personal fetch lands", async () => {
    api.fetchPost.mockResolvedValue(fact({ like_count: 4, liked_by_me: true }));
    renderDetail(fact({ like_count: 4 }), "verified");
    expect(await screen.findByRole("button", { name: "Like 4" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("counts a new comment in the heading and the action row, and a deleted one back out", async () => {
    social.createComment.mockResolvedValue(comment({ id: "mine", content: "Mine", is_mine: true }));
    social.deleteComment.mockResolvedValue(undefined);
    api.fetchPost.mockResolvedValue(fact());
    renderDetail(fact(), "verified");
    await userEvent.type(await screen.findByRole("textbox", { name: "Add a comment" }), "Mine");
    await userEvent.click(screen.getByRole("button", { name: "Comment" }));
    expect(await screen.findByRole("heading", { name: "Comments (1)" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Comments 1" })).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await userEvent.click(await screen.findByRole("button", { name: "Delete comment" }));
    expect(await screen.findByRole("heading", { name: "Comments (0)" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Comments 0" })).toBeInTheDocument();
  });

  it("has no discussion on a removed post's tombstone, and none for its author either", async () => {
    const removed = fact({ status: "removed", content: "" });
    renderDetail(removed, "anonymous");
    expect(screen.queryByRole("heading", { name: /Comments/ })).toBeNull();
    api.fetchPost.mockResolvedValue(fact({ status: "removed", is_mine: true }));
    renderDetail(removed, "verified");
    await screen.findByText(/Only you can see this text/);
    expect(screen.queryByRole("heading", { name: /Comments/ })).toBeNull();
    expect(social.fetchComments).not.toHaveBeenCalled();
  });
});

describe("PostDetail report (Part 8)", () => {
  // By someone else than the test session's user (`u-1`).
  const theirs = (overrides = {}) => fact({ author: BO, ...overrides });

  it("offers Report in the action row, with its word, to a signed-in reader", async () => {
    api.fetchPost.mockResolvedValue(theirs());
    renderDetail(theirs(), "verified");
    const button = await screen.findByRole("button", { name: "Report" });
    expect(within(button).getByText("Report", { selector: "[aria-hidden]" })).toHaveClass(
      "sm:inline",
    );
    // In the same row as Like, Comments, Repost, Bookmark and Copy link.
    expect(button.closest(".border-t")).toContainElement(
      screen.getByRole("button", { name: "Copy link" }),
    );
  });

  it("sends a log-in link to a visitor", () => {
    renderDetail(theirs(), "anonymous");
    expect(screen.getByRole("link", { name: "Report" })).toHaveAttribute(
      "href",
      `/login?next=%2Fp%2F${ID}`,
    );
  });

  it("reports from the page: the dialog quotes the claim, and the button follows", async () => {
    reports.reportPost.mockResolvedValue({ reported: true });
    api.fetchPost.mockResolvedValue(theirs());
    renderDetail(theirs(), "verified");
    await userEvent.click(await screen.findByRole("button", { name: "Report" }));
    const dialog = screen.getByRole("dialog", { name: "Report this post" });
    expect(within(dialog).getByText(/Solar capacity grew 30% last year\./)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("radio", { name: /False or inaccurate/ }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Submit report" }));
    expect(reports.reportPost).toHaveBeenCalledWith(ID, { reason: "inaccurate", details: "" });
    expect(await screen.findByRole("button", { name: /You reported this/ })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("shows 'You reported this' when the signed-in view says so", async () => {
    api.fetchPost.mockResolvedValue(theirs({ reported_by_me: true }));
    renderDetail(theirs(), "verified");
    expect(await screen.findByRole("button", { name: /You reported this/ })).toBeInTheDocument();
  });

  it("has no Report on your own post", async () => {
    api.fetchPost.mockResolvedValue(fact({ is_mine: true }));
    renderDetail(fact({ is_mine: true }), "verified");
    await screen.findByRole("button", { name: "Delete" });
    expect(screen.queryByRole("button", { name: /report/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /report/i })).not.toBeInTheDocument();
  });

  it("has no Report on a removed post's tombstone", async () => {
    renderDetail(theirs({ status: "removed", content: "" }), "anonymous");
    expect(screen.queryByRole("link", { name: /report/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /report/i })).not.toBeInTheDocument();
  });
});

// ---------- Part 11: appeals ----------

const appeals = vi.hoisted(() => ({ appealPost: vi.fn() }));
vi.mock("@/features/appeals/appeals-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/appeals/appeals-api")>()),
  ...appeals,
}));

const FALSE_MINE = () =>
  fact({
    status: "verified_false",
    verdict_source: "pipeline",
    confidence_score: "93.00",
    is_mine: true,
    can_appeal: true,
  });
const UNDER_APPEAL = () =>
  fact({
    status: "under_review",
    is_mine: true,
    can_appeal: false,
    appeal_status: "open",
  });

describe("PostDetail (appeals)", () => {
  beforeEach(() => {
    appeals.appealPost.mockReset();
  });

  it("offers the author of a FALSE post 'Request another look' at the bottom of the verdict", async () => {
    api.fetchPost.mockResolvedValue(FALSE_MINE());
    renderDetail(fact({ status: "verified_false", verdict_source: "pipeline" }), "verified");
    const button = await screen.findByRole("button", { name: "Request another look" });
    expect(
      within(screen.getByRole("heading", { name: "Verdict" }).closest("section")!).getByRole(
        "button",
        { name: "Request another look" },
      ),
    ).toBe(button);
    expect(button).toHaveClass("ml-auto");
  });

  it("leaves no empty row under the verdict when there is nothing to ask", async () => {
    api.fetchPost.mockResolvedValue(
      fact({ status: "under_review", is_mine: true, can_appeal: false, appeal_status: "open" }),
    );
    renderDetail(fact({ status: "under_review" }), "verified");
    await screen.findByText("APPEAL PENDING");
    const verdict = screen.getByRole("heading", { name: "Verdict" }).closest("section")!;
    expect(verdict.querySelector(".pt-space-xs")).toBeNull();
  });

  it("offers it to nobody else: not to a reader, not to a visitor", async () => {
    api.fetchPost.mockResolvedValue(
      fact({ status: "verified_false", is_mine: false, can_appeal: false }),
    );
    renderDetail(fact({ status: "verified_false" }), "verified");
    await waitFor(() => expect(api.fetchPost).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Request another look" })).toBeNull();
    renderDetail(fact({ status: "verified_false" }), "anonymous");
    expect(screen.queryByRole("button", { name: "Request another look" })).toBeNull();
  });

  it("offers it on no other status, even to the author", async () => {
    api.fetchPost.mockResolvedValue(
      fact({ status: "verified_true", is_mine: true, can_appeal: false }),
    );
    renderDetail(fact({ status: "verified_true" }), "verified");
    await screen.findByRole("button", { name: "Delete" });
    expect(screen.queryByRole("button", { name: "Request another look" })).toBeNull();
  });

  it("sends the request, patches the page and shows UNDER REVIEW with the chip and the line", async () => {
    const user = userEvent.setup();
    api.fetchPost.mockResolvedValue(FALSE_MINE());
    appeals.appealPost.mockResolvedValue(UNDER_APPEAL());
    renderDetail(fact({ status: "verified_false", verdict_source: "pipeline" }), "verified");
    await user.click(await screen.findByRole("button", { name: "Request another look" }));
    await user.type(
      screen.getByRole("textbox", { name: "Why should we look again?" }),
      "The source was updated.",
    );
    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("APPEAL PENDING")).toBeInTheDocument();
    expect(appeals.appealPost).toHaveBeenCalledWith(ID, { reason: "The source was updated." });
    expect(screen.getAllByText("UNDER REVIEW").length).toBeGreaterThan(0);
    expect(screen.getByText(/will review it/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request another look" })).toBeNull();
  });

  it("refetches the post when the server says an appeal exists already", async () => {
    const user = userEvent.setup();
    api.fetchPost.mockResolvedValue(FALSE_MINE());
    appeals.appealPost.mockRejectedValue(
      new ApiError({ status: 409, code: "already_appealed", detail: "" }),
    );
    renderDetail(fact({ status: "verified_false" }), "verified");
    await user.click(await screen.findByRole("button", { name: "Request another look" }));
    api.fetchPost.mockResolvedValue(
      fact({ status: "under_review", is_mine: true, can_appeal: false, appeal_status: "open" }),
    );
    const before = api.fetchPost.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("APPEAL PENDING")).toBeInTheDocument();
    expect(api.fetchPost.mock.calls.length).toBeGreaterThan(before);
  });

  it.each([
    ["verified_true", "overturned", "A moderator reversed the decision."],
    ["verified_false", "upheld", "A moderator reviewed it, and the FALSE label stays."],
  ] as const)(
    "tells the author what became of the appeal: %s / %s",
    async (status, appeal_status, words) => {
      api.fetchPost.mockResolvedValue(
        fact({ status, is_mine: true, can_appeal: false, appeal_status }),
      );
      renderDetail(fact({ status }), "verified");
      expect(await screen.findByText(new RegExp(words.replace(".", "\\.")))).toBeInTheDocument();
      expect(screen.queryByText("APPEAL PENDING")).toBeNull();
      expect(screen.queryByRole("button", { name: "Request another look" })).toBeNull();
    },
  );

  it("tells the author of a restored opinion too (an opinion has no verdict block to hold the line)", async () => {
    api.fetchPost.mockResolvedValue(
      makePost({
        id: ID,
        status: "published",
        post_type: "opinion",
        is_mine: true,
        can_appeal: false,
        appeal_status: "overturned",
      }),
    );
    renderDetail(makePost({ id: ID, is_mine: false }), "verified");
    expect(await screen.findByText(/A moderator reversed the decision/)).toBeInTheDocument();
    expect(screen.getByText("Opinions aren't fact-checked.")).toBeInTheDocument();
  });

  it("says nothing about appeals to a reader", () => {
    renderDetail(fact({ status: "verified_false", appeal_status: null }), "anonymous");
    expect(screen.queryByText(/You asked for another look/)).toBeNull();
  });
});

describe("PostDetail (the author's removed post)", () => {
  const mineRemoved = (overrides = {}) =>
    fact({
      status: "removed",
      is_mine: true,
      can_appeal: true,
      content: "My removed claim",
      removal_reason: "Personal attack",
      ...overrides,
    });

  it("keeps the claim as the h1 and adds the note, the reason, the sources, Delete and the button", async () => {
    api.fetchPost.mockResolvedValue(mineRemoved());
    renderDetail(fact({ status: "removed", content: "" }), "verified");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "“My removed claim”",
    );
    expect(screen.getByText(/Only you can see this text/)).toBeInTheDocument();
    expect(screen.getByText("Reason given: Personal attack")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sources (2)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request another look" })).toBeInTheDocument();
  });

  it("has no action bar, verdict or discussion", async () => {
    api.fetchPost.mockResolvedValue(mineRemoved());
    renderDetail(fact({ status: "removed", content: "" }), "verified");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("heading", { name: "Verdict" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Like|Repost|Bookmark|Report/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy link" })).toBeNull();
    expect(social.fetchComments).not.toHaveBeenCalled();
  });

  it("sends the appeal from the page and shows the chip", async () => {
    const user = userEvent.setup();
    api.fetchPost.mockResolvedValue(mineRemoved());
    appeals.appealPost.mockResolvedValue(mineRemoved({ can_appeal: false, appeal_status: "open" }));
    renderDetail(fact({ status: "removed", content: "" }), "verified");
    await user.click(await screen.findByRole("button", { name: "Request another look" }));
    expect(screen.getByText(/A moderator removed your post\./)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("APPEAL PENDING")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request another look" })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("My removed claim");
  });

  it("shows a visitor the notice with the author row and no appeal", () => {
    renderDetail(
      fact({ status: "removed", content: "", removal_reason: "leaked", can_appeal: true }),
    );
    expect(screen.getByText(DETAIL_MESSAGES.removed)).toBeInTheDocument();
    expect(screen.queryByText(/leaked/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Request another look" })).toBeNull();
  });

  it("deletes from the card's footer as before", async () => {
    const user = userEvent.setup();
    api.fetchPost.mockResolvedValue(mineRemoved());
    renderDetail(fact({ status: "removed", content: "" }), "verified");
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

describe("PostDetail: how this was checked (Part 11D)", () => {
  it("shows the stats section for a fact, between the verdict and the sources", async () => {
    renderDetail(fact());
    const heading = await screen.findByRole("heading", { name: "How this was checked" });
    const verdict = screen.getByRole("heading", { name: "Verdict" });
    const sources = screen.getByRole("heading", { name: /^Sources/ });
    expect(
      verdict.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      heading.compareDocumentPosition(sources) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(api.fetchPostStats).toHaveBeenCalledWith(ID, expect.any(AbortSignal));
  });

  it("shows nothing and asks for nothing on an opinion", () => {
    renderDetail(makePost({ id: ID, status: "published", is_mine: false }));
    expect(screen.queryByRole("heading", { name: "How this was checked" })).not.toBeInTheDocument();
    expect(api.fetchPostStats).not.toHaveBeenCalled();
  });

  it("keeps the page whole when the stats can't be loaded", async () => {
    api.fetchPostStats.mockRejectedValue(new Error("down"));
    renderDetail(fact());
    await waitFor(() => expect(api.fetchPostStats).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { name: "How this was checked" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });
});
