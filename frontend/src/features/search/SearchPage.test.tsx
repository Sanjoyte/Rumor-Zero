import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  feedEntry,
  makePost,
  renderWithComposer,
  renderWithSessionAndToast,
} from "@/features/posts/test-helpers";
import { makeRow } from "@/features/social/test-helpers";
import { ApiError } from "@/lib/api/client";
import { SearchPage } from "./SearchPage";

const api = vi.hoisted(() => ({ searchPosts: vi.fn(), searchPeople: vi.fn() }));
vi.mock("./search-api", () => api);
vi.mock("@/features/social/social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/social/social-api")>()),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
}));
const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), query: "" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: nav.replace, prefetch: vi.fn() }),
  usePathname: () => "/search",
  useSearchParams: () => new URLSearchParams(nav.query),
}));

const postPage = (contents: string[], nextCursor: string | null = null) => ({
  items: contents.map((content) =>
    feedEntry(makePost({ id: `p-${content}`, content, is_mine: false })),
  ),
  nextCursor,
});
const peoplePage = (names: string[], nextCursor: string | null = null) => ({
  items: names.map((name) => makeRow({ id: `id-${name}`, username: name, display_name: name })),
  nextCursor,
});

beforeEach(() => {
  nav.push.mockReset();
  nav.replace.mockReset();
  nav.query = "";
  api.searchPosts.mockReset();
  api.searchPosts.mockResolvedValue(postPage(["Storm warning tonight"]));
  api.searchPeople.mockReset();
  api.searchPeople.mockResolvedValue(peoplePage(["ada"]));
});

const cards = () => screen.queryAllByRole("article");
const marks = () => [...document.querySelectorAll("mark")].map((mark) => mark.textContent);
const render = (kind: "anonymous" | "verified" = "anonymous") =>
  renderWithComposer(<SearchPage />, kind);

describe("SearchPage: no query", () => {
  it("shows the prompt, the box, the tabs and the chips, and asks for nothing", async () => {
    render();
    expect(await screen.findByText("Search Rumor Zero")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Search" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Search query" })).toHaveValue("");
    expect(screen.getByRole("tab", { name: "Posts" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "People" })).toBeInTheDocument();
    for (const name of ["All", "Facts", "Opinions", "Verified", "FALSE", "Under review"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    expect(api.searchPosts).not.toHaveBeenCalled();
    expect(api.searchPeople).not.toHaveBeenCalled();
  });

  it("treats a blank q as no query", async () => {
    nav.query = "q=%20%20";
    render();
    expect(await screen.findByText("Search Rumor Zero")).toBeInTheDocument();
    expect(api.searchPosts).not.toHaveBeenCalled();
  });
});

describe("SearchPage: posts", () => {
  it("searches for q with the chip and shows the cards with the terms marked", async () => {
    nav.query = "q=storm&filter=verified";
    render();
    await waitFor(() => expect(cards()).toHaveLength(1));
    expect(api.searchPosts).toHaveBeenCalledWith(
      "storm",
      "verified",
      null,
      expect.any(AbortSignal),
    );
    expect(marks()).toEqual(["Storm"]);
    expect(screen.getByRole("textbox", { name: "Search query" })).toHaveValue("storm");
    expect(screen.getByRole("button", { name: "Verified" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("shows skeletons while loading", () => {
    nav.query = "q=storm";
    api.searchPosts.mockReturnValue(new Promise(() => {}));
    render();
    expect(screen.getByText("Loading posts…")).toBeInTheDocument();
  });

  it("says when nothing matched, quoting the query", async () => {
    nav.query = "q=zzz";
    api.searchPosts.mockResolvedValue(postPage([]));
    render();
    expect(await screen.findByText("No results for “zzz”")).toBeInTheDocument();
    expect(screen.getByText("Try different words or remove a filter.")).toBeInTheDocument();
  });

  it("shows an error with Try again, which asks again", async () => {
    nav.query = "q=storm";
    api.searchPosts.mockRejectedValueOnce(
      new ApiError({ status: 500, code: "error", detail: "x" }),
    );
    render();
    expect(await screen.findByText("Couldn't load posts")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(cards()).toHaveLength(1));
    expect(api.searchPosts).toHaveBeenCalledTimes(2);
  });

  it("explains the rate limit and when to try again", async () => {
    nav.query = "q=storm";
    api.searchPosts.mockRejectedValue(
      new ApiError({ status: 429, code: "throttled", detail: "x", retryAfter: 40 }),
    );
    render();
    expect(
      await screen.findByText("You're going too fast. Try again in a minute."),
    ).toBeInTheDocument();
  });

  it("loads more with the cursor it was given and says it is caught up at the end", async () => {
    nav.query = "q=storm";
    api.searchPosts
      .mockResolvedValueOnce(postPage(["Storm one"], "2"))
      .mockResolvedValueOnce(postPage(["Storm two"], null));
    render();
    await waitFor(() => expect(cards()).toHaveLength(1));
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(api.searchPosts).toHaveBeenLastCalledWith("storm", "all", "2", expect.any(AbortSignal));
    expect(screen.getByText("You're caught up.")).toBeInTheDocument();
  });

  it("says results stop at 100 when the last page was the cap", async () => {
    nav.query = "q=storm";
    api.searchPosts.mockResolvedValue({
      items: Array.from({ length: 100 }, (_, n) =>
        feedEntry(makePost({ id: `p-${n}`, content: `Storm ${n}`, is_mine: false })),
      ),
      nextCursor: null,
    });
    render();
    expect(
      await screen.findByText(
        "That's the first 100 results. Try more specific words to narrow them down.",
      ),
    ).toBeInTheDocument();
  });

  it("works when React mounts it twice (StrictMode)", async () => {
    nav.query = "q=storm";
    renderWithComposer(
      <StrictMode>
        <SearchPage />
      </StrictMode>,
      "verified",
    );
    await waitFor(() => expect(cards()).toHaveLength(1));
  });

  it("searches again when the address brings another query or chip", async () => {
    nav.query = "q=storm";
    const view = renderWithSessionAndToast(<SearchPage />, "anonymous");
    await waitFor(() => expect(cards()).toHaveLength(1));
    nav.query = "q=flood&filter=false";
    view.rerender(<SearchPage />);
    await waitFor(() =>
      expect(api.searchPosts).toHaveBeenLastCalledWith(
        "flood",
        "false",
        null,
        expect.any(AbortSignal),
      ),
    );
  });
});

describe("SearchPage: waiting for the session", () => {
  it("asks for nothing until the session is known, so the first request carries the token", async () => {
    nav.query = "q=storm";
    renderWithComposer(<SearchPage />, "loading");
    expect(await screen.findByText("Loading posts…")).toBeInTheDocument();
    expect(api.searchPosts).not.toHaveBeenCalled();
  });

  it("does the same for people", async () => {
    nav.query = "q=ada&type=users";
    renderWithComposer(<SearchPage />, "loading");
    expect(await screen.findByText("Loading people…")).toBeInTheDocument();
    expect(api.searchPeople).not.toHaveBeenCalled();
  });
});

describe("SearchPage: tabs and chips change the address", () => {
  it("a chip replaces the address and keeps q", async () => {
    nav.query = "q=storm";
    render();
    await userEvent.click(screen.getByRole("button", { name: "FALSE" }));
    expect(nav.replace).toHaveBeenCalledWith("/search?q=storm&filter=false");
    expect(nav.push).not.toHaveBeenCalled();
  });

  it("pressing the chosen chip again goes back to All", async () => {
    nav.query = "q=storm&filter=review";
    render();
    await userEvent.click(screen.getByRole("button", { name: "Under review" }));
    expect(nav.replace).toHaveBeenCalledWith("/search?q=storm");
  });

  it("the People tab pushes the address, keeps q and drops the chip", async () => {
    nav.query = "q=storm&filter=false";
    render();
    await userEvent.click(screen.getByRole("tab", { name: "People" }));
    expect(nav.push).toHaveBeenCalledWith("/search?q=storm&type=users");
  });

  it("the Posts tab comes back to the default chip", async () => {
    nav.query = "q=storm&type=users";
    render();
    await userEvent.click(screen.getByRole("tab", { name: "Posts" }));
    expect(nav.push).toHaveBeenCalledWith("/search?q=storm");
  });

  it("clicking the tab you are on does nothing", async () => {
    nav.query = "q=storm";
    render();
    await userEvent.click(screen.getByRole("tab", { name: "Posts" }));
    expect(nav.push).not.toHaveBeenCalled();
  });
});

describe("SearchPage: people", () => {
  beforeEach(() => {
    nav.query = "q=ada&type=users";
  });

  it("shows the people as rows with a Follow button and the credibility chip", async () => {
    api.searchPeople.mockResolvedValue({
      items: [
        makeRow({
          id: "u-ada",
          username: "ada",
          display_name: "Ada Lane",
          reputation: { score: 82, sample: 9 },
          counts: { verified: 4 },
        }),
      ],
      nextCursor: null,
    });
    render();
    await waitFor(() => expect(cards()).toHaveLength(1));
    expect(api.searchPeople).toHaveBeenCalledWith("ada", null, expect.any(AbortSignal));
    const row = within(cards()[0]);
    expect(row.getByRole("link", { name: /Ada Lane/ })).toHaveAttribute("href", "/u/ada");
    expect(row.getByText("Credibility 82")).toBeInTheDocument();
    expect(row.getByText(/4\s+verified/)).toBeInTheDocument();
    expect(row.getByRole("link", { name: "Follow" })).toHaveAttribute(
      "href",
      "/login?next=%2Fu%2Fada",
    );
    expect(marks().length).toBeGreaterThan(0);
  });

  it("has no chips on this tab", async () => {
    render();
    await waitFor(() => expect(cards()).toHaveLength(1));
    expect(screen.queryByRole("group", { name: "Filter posts" })).toBeNull();
    expect(screen.getByRole("tab", { name: "People" })).toHaveAttribute("aria-selected", "true");
  });

  it("says when nobody matched", async () => {
    api.searchPeople.mockResolvedValue(peoplePage([]));
    render();
    expect(await screen.findByText("No people found for “ada”")).toBeInTheDocument();
  });

  it("loads more people with the cursor and ends with That's everyone.", async () => {
    api.searchPeople
      .mockResolvedValueOnce(peoplePage(["ada_a"], "2"))
      .mockResolvedValueOnce(peoplePage(["ada_b"], null));
    render();
    await waitFor(() => expect(cards()).toHaveLength(1));
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(api.searchPeople).toHaveBeenLastCalledWith("ada", "2", expect.any(AbortSignal));
    expect(screen.getByText("That's everyone.")).toBeInTheDocument();
  });

  it("shows an error with Try again, and the rate limit in words", async () => {
    api.searchPeople.mockRejectedValueOnce(
      new ApiError({ status: 429, code: "throttled", detail: "x", retryAfter: 30 }),
    );
    render();
    expect(
      await screen.findByText("You're going too fast. Try again in a minute."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(cards()).toHaveLength(1));
  });

  it("keeps the earlier rows and offers another try when Load more fails", async () => {
    api.searchPeople
      .mockResolvedValueOnce(peoplePage(["ada_a"], "2"))
      .mockRejectedValueOnce(new ApiError({ status: 500, code: "error", detail: "x" }));
    render();
    await waitFor(() => expect(cards()).toHaveLength(1));
    await userEvent.click(screen.getByRole("button", { name: /Load more/ }));
    expect(await screen.findByText(/Couldn't load more people/)).toBeInTheDocument();
    expect(cards()).toHaveLength(1);
  });

  it("says results stop at 100", async () => {
    api.searchPeople.mockResolvedValue(
      peoplePage(Array.from({ length: 100 }, (_, n) => `ada_${n}`)),
    );
    render();
    expect(await screen.findByText(/That's the first 100 results/)).toBeInTheDocument();
  });
});
