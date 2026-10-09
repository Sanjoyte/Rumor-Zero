import { StrictMode } from "react";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { DETAIL_MESSAGES, PostDetail } from "./PostDetail";
import { makePost, renderWithComposer, type SessionKind } from "./test-helpers";

const api = vi.hoisted(() => ({
  fetchPost: vi.fn(),
  deletePost: vi.fn(),
  fetchStatuses: vi.fn(),
  fetchRecentFeed: vi.fn(),
  fetchFactQuota: vi.fn(),
}));
vi.mock("./posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./posts-api")>()),
  ...api,
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

  it("shows a moderator's verdict and note, and an emergency chip", () => {
    renderDetail(
      fact({
        status: "verified_false",
        verdict_source: "moderator",
        verdict_note: "The report says otherwise.",
        emergency_active: true,
      }),
    );
    expect(screen.getByText("FALSE · REVIEWED")).toBeInTheDocument();
    expect(screen.getByText("Reviewed by a moderator")).toBeInTheDocument();
    expect(screen.getByText(/The report says otherwise\./)).toBeInTheDocument();
    expect(screen.getByText("EMERGENCY")).toBeInTheDocument();
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
