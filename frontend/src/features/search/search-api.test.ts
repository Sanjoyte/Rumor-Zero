import { beforeEach, describe, expect, it, vi } from "vitest";

const client = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  api: client,
}));

import { searchPeople, searchPosts } from "./search-api";

beforeEach(() => client.get.mockReset());

describe("searchPosts", () => {
  it("reads the first page as items and the next cursor", async () => {
    client.get.mockResolvedValue({
      pinned: [],
      pinned_total: 0,
      results: [1, 2],
      next_cursor: "2",
    });
    const signal = new AbortController().signal;
    expect(await searchPosts("storm", "all", null, signal)).toEqual({
      items: [1, 2],
      nextCursor: "2",
    });
    expect(client.get).toHaveBeenCalledWith("/v1/search/?q=storm&type=posts", { signal });
  });

  it("sends the chip as the API's filter and the cursor as it came", async () => {
    client.get.mockResolvedValue({ pinned: [], pinned_total: 0, results: [], next_cursor: null });
    await searchPosts("storm", "verified", "3");
    expect(client.get).toHaveBeenLastCalledWith(
      "/v1/search/?q=storm&type=posts&status=verified_true&cursor=3",
      { signal: undefined },
    );
    await searchPosts("storm", "facts", null);
    expect(client.get).toHaveBeenLastCalledWith("/v1/search/?q=storm&type=posts&post_type=fact", {
      signal: undefined,
    });
  });

  it("encodes & # % + spaces, quotes and emoji", async () => {
    client.get.mockResolvedValue({ pinned: [], pinned_total: 0, results: [], next_cursor: null });
    await searchPosts('a&b #1 100% +x "q" 😀', "all", null);
    const path = client.get.mock.calls[0][0] as string;
    const query = new URLSearchParams(path.split("?")[1]);
    expect(query.get("q")).toBe('a&b #1 100% +x "q" 😀');
    expect([...query.keys()]).toEqual(["q", "type"]);
    expect(path).not.toMatch(/[ "#]/);
  });
});

describe("searchPeople", () => {
  it("asks for users and returns rows and the cursor", async () => {
    client.get.mockResolvedValue({ results: [{ id: "u" }], next_cursor: "2" });
    expect(await searchPeople("@ada", null)).toEqual({ items: [{ id: "u" }], nextCursor: "2" });
    expect(client.get).toHaveBeenCalledWith("/v1/search/?q=%40ada&type=users", {
      signal: undefined,
    });
    await searchPeople("ada", "2");
    expect(client.get).toHaveBeenLastCalledWith("/v1/search/?q=ada&type=users&cursor=2", {
      signal: undefined,
    });
  });
});
