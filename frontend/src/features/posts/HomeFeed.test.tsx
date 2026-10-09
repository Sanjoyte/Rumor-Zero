import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
  createPost: vi.fn(),
  fetchFactQuota: vi.fn(),
  fetchRecentFeed: vi.fn(),
}));
vi.mock("./posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./posts-api")>()),
  ...api,
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
  api.createPost.mockReset();
  api.fetchFactQuota.mockReset();
  api.fetchFactQuota.mockResolvedValue(makeQuota());
  api.fetchRecentFeed.mockReset();
  api.fetchRecentFeed.mockResolvedValue(page(["a", "b"]));
});

function renderHome(kind: SessionKind = "verified") {
  return renderWithComposer(<HomeFeed />, kind);
}

const cards = () => screen.queryAllByRole("article");

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
});
