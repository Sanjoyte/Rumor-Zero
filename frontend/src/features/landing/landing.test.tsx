import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LandingPage from "@/app/(marketing)/page";
import { feedEntry, makePost, renderWithSessionAndToast } from "@/features/posts/test-helpers";

const api = vi.hoisted(() => ({ fetchRecentFeed: vi.fn() }));
vi.mock("@/features/posts/posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/posts/posts-api")>()),
  ...api,
}));

const page = (n: number) => ({
  items: Array.from({ length: n }, (_, i) =>
    feedEntry(makePost({ id: `p${i}`, content: `Post number ${i}`, is_mine: false })),
  ),
  nextCursor: null,
});

beforeEach(() => {
  api.fetchRecentFeed.mockReset();
  api.fetchRecentFeed.mockResolvedValue(page(6));
});

describe("landing page", () => {
  it("shows the hero, three feature cards and no Stitch leftovers", async () => {
    const { container } = renderWithSessionAndToast(<LandingPage />, "anonymous");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "opinions are labelled, and facts are checked",
    );
    expect(screen.getByRole("heading", { name: /1\. You say what it is/ })).toBeVisible();
    expect(screen.getByRole("heading", { name: /2\. Facts are checked/ })).toBeVisible();
    expect(screen.getByRole("heading", { name: /3\. Colour means the result/ })).toBeVisible();
    await screen.findByText(/Post number 0/);
    for (const forbidden of [
      "Epistemic",
      "Network Inc",
      "Calibration Edition",
      "guaranteed",
      "Evidence-First",
      "Zero-bias",
      "Verification Ledger",
    ]) {
      expect(container.textContent).not.toContain(forbidden);
    }
  });

  it("offers sign-up and log-in to a visitor", async () => {
    renderWithSessionAndToast(<LandingPage />, "anonymous");
    expect(await screen.findByRole("link", { name: "Create account" })).toHaveAttribute(
      "href",
      "/signup",
    );
    expect(screen.getByRole("link", { name: "I already have an account" })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(screen.queryByRole("link", { name: "Go to your feed" })).toBeNull();
  });

  it("offers a signed-in visitor 'Go to your feed'", async () => {
    renderWithSessionAndToast(<LandingPage />, "verified");
    expect(await screen.findByRole("link", { name: "Go to your feed" })).toHaveAttribute(
      "href",
      "/home",
    );
    expect(screen.queryByRole("link", { name: "Create account" })).toBeNull();
  });

  it("previews four recent posts", async () => {
    renderWithSessionAndToast(<LandingPage />, "anonymous");
    await screen.findByText(/Post number 3/);
    expect(screen.queryByText(/Post number 4/)).toBeNull();
    expect(screen.getAllByRole("article")).toHaveLength(4);
    expect(screen.getByRole("link", { name: "See more posts" })).toHaveAttribute("href", "/home");
  });

  it("skips removed posts and reposts", async () => {
    api.fetchRecentFeed.mockResolvedValue({
      items: [
        feedEntry(makePost({ id: "gone", content: "Removed words", status: "removed" })),
        feedEntry(makePost({ id: "ok", content: "Kept words" })),
      ],
      nextCursor: null,
    });
    renderWithSessionAndToast(<LandingPage />, "anonymous");
    await screen.findByText(/Kept words/);
    expect(screen.queryByText(/Removed words/)).toBeNull();
  });

  it("shows a skeleton first, then a quiet notice when the feed fails", async () => {
    api.fetchRecentFeed.mockRejectedValue(new Error("down"));
    const { container } = renderWithSessionAndToast(<LandingPage />, "anonymous");
    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
    await waitFor(() =>
      expect(screen.getByText("Recent posts couldn’t be loaded right now.")).toBeVisible(),
    );
    expect(screen.getByRole("heading", { level: 1 })).toBeVisible();
  });

  it("shows an empty state when there are no posts", async () => {
    api.fetchRecentFeed.mockResolvedValue({ items: [], nextCursor: null });
    renderWithSessionAndToast(<LandingPage />, "anonymous");
    expect(await screen.findByText("No posts yet")).toBeVisible();
  });
});
