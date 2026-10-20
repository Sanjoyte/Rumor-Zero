import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import {
  deletePost,
  fetchEmergencies,
  fetchPost,
  fetchRecentFeed,
  fetchStatuses,
  MAX_STATUS_IDS,
} from "./posts-api";

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  api: { get: vi.fn(), post: vi.fn(), del: vi.fn() },
}));

const ID = "11111111-1111-4111-8111-111111111111";

beforeEach(() => vi.clearAllMocks());

describe("fetchPost / deletePost", () => {
  it("reads and deletes /v1/posts/{id}/ with the usual token handling", async () => {
    vi.mocked(api.get).mockResolvedValue({ id: ID });
    await fetchPost(ID);
    expect(api.get).toHaveBeenCalledWith(`/v1/posts/${ID}/`, { signal: undefined });
    await deletePost(ID);
    expect(api.del).toHaveBeenCalledWith(`/v1/posts/${ID}/`);
  });

  it("encodes the id", async () => {
    await fetchPost("a/b");
    expect(vi.mocked(api.get).mock.calls[0][0]).toBe("/v1/posts/a%2Fb/");
  });
});

describe("fetchStatuses", () => {
  it("sends the ids comma-separated, never the token, and unwraps the results", async () => {
    const results = [{ id: ID, status: "pending", confidence_score: null, verdict_source: null }];
    vi.mocked(api.get).mockResolvedValue({ results });
    const signal = new AbortController().signal;
    expect(await fetchStatuses([ID, "b"], signal)).toEqual(results);
    expect(api.get).toHaveBeenCalledWith(`/v1/posts/status/?ids=${ID}%2Cb`, {
      signal,
      token: false,
    });
  });

  it("asks about at most 50 posts", async () => {
    vi.mocked(api.get).mockResolvedValue({ results: [] });
    const ids = Array.from({ length: 70 }, (_, i) => `p${i}`);
    await fetchStatuses(ids);
    const url = vi.mocked(api.get).mock.calls[0][0] as string;
    expect(decodeURIComponent(url.split("ids=")[1]).split(",")).toHaveLength(MAX_STATUS_IDS);
  });
});

describe("the pinned emergencies (Part 11C)", () => {
  it("returns the first page's pinned list as the feed's head", async () => {
    const pinned = [{ id: "p" }];
    vi.mocked(api.get).mockResolvedValue({
      pinned,
      pinned_total: 4,
      results: [],
      next_cursor: "c",
    });
    expect(await fetchRecentFeed(null)).toEqual({
      items: [],
      nextCursor: "c",
      head: { pinned, pinnedTotal: 4 },
    });
  });

  it("lists every active emergency of a feed, with the cursor", async () => {
    vi.mocked(api.get).mockResolvedValue({ results: [{ id: "p" }], next_cursor: "n" });
    const signal = new AbortController().signal;
    expect(await fetchEmergencies("recent", null, signal)).toEqual({
      items: [{ id: "p" }],
      nextCursor: "n",
    });
    expect(api.get).toHaveBeenCalledWith("/v1/posts/emergencies/?feed=recent", { signal });
    await fetchEmergencies("following", "a b/c");
    expect(vi.mocked(api.get).mock.calls[1][0]).toBe(
      "/v1/posts/emergencies/?feed=following&cursor=a+b%2Fc",
    );
  });
});
