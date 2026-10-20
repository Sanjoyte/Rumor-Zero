import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Post } from "@/lib/api/types";
import { PinnedEmergencies, PinnedEmergenciesBar } from "./PinnedEmergencies";
import { collapseKey } from "./pinned-collapse";
import { makePost } from "./test-helpers";

const urgent = (id: string, overrides: Partial<Post> = {}) =>
  makePost({
    id,
    content: `Warning ${id}`,
    post_type: "fact",
    status: "pending",
    is_emergency: true,
    emergency_active: true,
    is_mine: false,
    ...overrides,
  });

const THREE = [urgent("a"), urgent("b"), urgent("c")];

const section = () => screen.queryByRole("region", { name: /emergency posts/i });
const cards = () => screen.queryAllByRole("article");
const hideButton = () => screen.getByRole("button", { name: "Hide the emergency posts" });

beforeEach(() => {
  window.sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("PinnedEmergencies", () => {
  it("shows nothing when nothing is pinned", () => {
    const { container } = render(<PinnedEmergencies feed="recent" posts={[]} total={0} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows b1's banner and the pinned cards, newest first", () => {
    render(<PinnedEmergencies feed="recent" posts={THREE} total={3} />);
    const region = section()!;
    expect(
      within(region).getByRole("heading", { level: 2, name: "Emergency posts" }),
    ).toBeVisible();
    expect(within(region).getByText("Pinned for a limited time and checked first.")).toBeVisible();
    expect(cards().map((card) => card.textContent)).toEqual([
      expect.stringContaining("Warning a"),
      expect.stringContaining("Warning b"),
      expect.stringContaining("Warning c"),
    ]);
    expect(within(region).getAllByText("EMERGENCY")).toHaveLength(3);
    // Everything pinned is shown: no "Show all".
    expect(screen.queryByRole("button", { name: /Show all/ })).toBeNull();
  });

  it("renders the cards the caller gives it", () => {
    render(
      <PinnedEmergencies
        feed="recent"
        posts={THREE}
        total={3}
        renderCard={(post) => <p>card for {post.id}</p>}
      />,
    );
    expect(screen.getByText("card for b")).toBeInTheDocument();
  });

  it("offers Show all when more are pinned, and lists them in place", async () => {
    const all = [...THREE, urgent("d"), urgent("e")];
    const fetchAll = vi
      .fn()
      .mockResolvedValueOnce({ items: all.slice(0, 4), nextCursor: "n" })
      .mockResolvedValueOnce({ items: all.slice(4), nextCursor: null });
    render(<PinnedEmergencies feed="following" posts={THREE} total={5} fetchAll={fetchAll} />);
    expect(fetchAll).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Show all (5)" }));
    await waitFor(() => expect(cards()).toHaveLength(4));
    expect(fetchAll).toHaveBeenCalledWith(null, expect.any(AbortSignal));
    expect(screen.queryByRole("button", { name: /Show all/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    await waitFor(() => expect(cards()).toHaveLength(5));
    expect(fetchAll).toHaveBeenLastCalledWith("n", expect.any(AbortSignal));
    expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
  });

  it("asks the emergencies endpoint of its own feed by default", async () => {
    const posts = await import("./posts-api");
    const spy = vi.spyOn(posts, "fetchEmergencies").mockResolvedValue({
      items: THREE,
      nextCursor: null,
    });
    render(<PinnedEmergencies feed="following" posts={THREE} total={4} />);
    await userEvent.click(screen.getByRole("button", { name: "Show all (4)" }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0]).toBe("following");
  });

  it("leaves out a post the poll found FALSE or removed, and counts one fewer", () => {
    const hide = (post: Post) => post.id === "b";
    render(<PinnedEmergencies feed="recent" posts={THREE} total={4} hide={hide} />);
    expect(screen.queryByText(/Warning b/)).toBeNull();
    expect(cards()).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Show all (3)" })).toBeInTheDocument();
  });

  it("disappears when every pinned post is hidden", () => {
    render(<PinnedEmergencies feed="recent" posts={THREE} total={3} hide={() => true} />);
    expect(section()).toBeNull();
  });
});

describe("PinnedEmergencies: folding it away for this tab", () => {
  it("writes nothing to storage until × is pressed", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    render(<PinnedEmergencies feed="recent" posts={THREE} total={3} />);
    expect(setItem).not.toHaveBeenCalled();
    expect(window.sessionStorage.length).toBe(0);
  });

  it("folds to one line with ×, remembers the ids, and moves focus to Show", async () => {
    render(<PinnedEmergencies feed="recent" posts={THREE} total={4} />);
    await userEvent.click(hideButton());
    expect(cards()).toHaveLength(0);
    const bar = screen.getByRole("region", { name: "4 emergency posts pinned" });
    const show = within(bar).getByRole("button", { name: "Show" });
    expect(show).toHaveFocus();
    expect(JSON.parse(window.sessionStorage.getItem(collapseKey("recent"))!)).toEqual([
      "a",
      "b",
      "c",
    ]);
    // Per feed: the other tab's section is untouched.
    expect(window.sessionStorage.getItem(collapseKey("following"))).toBeNull();
  });

  it("opens again with Show, forgets the fold and gives × the focus back", async () => {
    render(<PinnedEmergencies feed="recent" posts={THREE} total={3} />);
    await userEvent.click(hideButton());
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(cards()).toHaveLength(3);
    expect(hideButton()).toHaveFocus();
    expect(window.sessionStorage.getItem(collapseKey("recent"))).toBeNull();
  });

  it("stays folded across a remount (another page and back)", () => {
    window.sessionStorage.setItem(collapseKey("recent"), JSON.stringify(["a", "b", "c"]));
    render(<PinnedEmergencies feed="recent" posts={THREE} total={3} />);
    expect(screen.getByRole("region", { name: "3 emergency posts pinned" })).toBeInTheDocument();
    expect(cards()).toHaveLength(0);
  });

  it("opens again by itself when a post that wasn't pinned before appears", () => {
    window.sessionStorage.setItem(collapseKey("recent"), JSON.stringify(["a", "b", "c"]));
    const { rerender } = render(<PinnedEmergencies feed="recent" posts={THREE} total={3} />);
    expect(cards()).toHaveLength(0);
    rerender(<PinnedEmergencies feed="recent" posts={[urgent("new"), ...THREE]} total={4} />);
    expect(cards()).toHaveLength(4);
  });

  it("stays folded when a pinned post expires and leaves", () => {
    window.sessionStorage.setItem(collapseKey("recent"), JSON.stringify(["a", "b", "c"]));
    render(<PinnedEmergencies feed="recent" posts={THREE.slice(1)} total={2} />);
    expect(screen.getByRole("region", { name: "2 emergency posts pinned" })).toBeInTheDocument();
  });

  it("ignores a malformed stored value", () => {
    window.sessionStorage.setItem(collapseKey("recent"), "{not json");
    render(<PinnedEmergencies feed="recent" posts={THREE} total={3} />);
    expect(cards()).toHaveLength(3);
  });

  it("still folds when storage refuses, until the page reloads", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    render(<PinnedEmergencies feed="following" posts={THREE} total={3} />);
    await userEvent.click(hideButton());
    expect(screen.getByRole("region", { name: "3 emergency posts pinned" })).toBeInTheDocument();
    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: "Show" }));
    });
    expect(cards()).toHaveLength(3);
  });
});

describe("PinnedEmergenciesBar", () => {
  it("says how many are pinned and offers Show", async () => {
    const onShow = vi.fn();
    render(<PinnedEmergenciesBar count={1} onShow={onShow} />);
    expect(screen.getByRole("region", { name: "1 emergency post pinned" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(onShow).toHaveBeenCalledTimes(1);
  });
});
