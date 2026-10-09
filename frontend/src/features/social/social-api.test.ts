import { beforeEach, describe, expect, it, vi } from "vitest";

const client = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), del: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  api: client,
}));

import {
  fetchConnections,
  fetchFollowingFeed,
  fetchProfile,
  fetchUserPosts,
  followUser,
  unfollowUser,
} from "./social-api";

beforeEach(() => {
  client.get.mockReset();
  client.post.mockReset();
  client.del.mockReset();
});

describe("social-api", () => {
  it("reads the Following feed with the cursor, as items and nextCursor", async () => {
    client.get.mockResolvedValue({ pinned: [], pinned_total: 0, results: [1], next_cursor: "c2" });
    const signal = new AbortController().signal;
    expect(await fetchFollowingFeed(null, signal)).toEqual({ items: [1], nextCursor: "c2" });
    expect(client.get).toHaveBeenCalledWith("/v1/feed/", { signal });
    await fetchFollowingFeed("a b/c");
    expect(client.get).toHaveBeenLastCalledWith("/v1/feed/?cursor=a+b%2Fc", { signal: undefined });
  });

  it("reads a profile, encoding the name", async () => {
    client.get.mockResolvedValue({ username: "bob" });
    await fetchProfile("bob");
    expect(client.get).toHaveBeenCalledWith("/v1/users/bob/", { signal: undefined });
    await fetchProfile("a/b");
    expect(client.get).toHaveBeenLastCalledWith("/v1/users/a%2Fb/", { signal: undefined });
  });

  it("reads a user's posts, with the type filter only when it isn't 'all'", async () => {
    client.get.mockResolvedValue({ results: [], next_cursor: null });
    await fetchUserPosts("bob", "all", null);
    expect(client.get).toHaveBeenLastCalledWith("/v1/users/bob/posts/", { signal: undefined });
    await fetchUserPosts("bob", "fact", null);
    expect(client.get).toHaveBeenLastCalledWith("/v1/users/bob/posts/?post_type=fact", {
      signal: undefined,
    });
    await fetchUserPosts("bob", "opinion", "c1");
    expect(client.get).toHaveBeenLastCalledWith(
      "/v1/users/bob/posts/?post_type=opinion&cursor=c1",
      {
        signal: undefined,
      },
    );
  });

  it("reads followers and following pages", async () => {
    client.get.mockResolvedValue({ results: [{ id: "x" }], next_cursor: "n" });
    expect(await fetchConnections("bob", "followers", null)).toEqual({
      items: [{ id: "x" }],
      nextCursor: "n",
    });
    expect(client.get).toHaveBeenLastCalledWith("/v1/users/bob/followers/", { signal: undefined });
    await fetchConnections("bob", "following", "c9");
    expect(client.get).toHaveBeenLastCalledWith("/v1/users/bob/following/?cursor=c9", {
      signal: undefined,
    });
  });

  it("follows with POST and unfollows with DELETE on the same path, with the token", async () => {
    client.post.mockResolvedValue({ is_following: true });
    expect(await followUser("bob")).toEqual({ is_following: true });
    expect(client.post).toHaveBeenCalledWith("/v1/users/bob/follow/");
    await unfollowUser("bob");
    expect(client.del).toHaveBeenCalledWith("/v1/users/bob/follow/");
  });

  it("never sends token: false (personal data rides on the token)", async () => {
    client.get.mockResolvedValue({ results: [], next_cursor: null });
    client.post.mockResolvedValue({});
    await fetchFollowingFeed(null);
    await fetchProfile("bob");
    await fetchUserPosts("bob", "all", null);
    await fetchConnections("bob", "followers", null);
    await followUser("bob");
    await unfollowUser("bob");
    for (const call of [
      ...client.get.mock.calls,
      ...client.post.mock.calls,
      ...client.del.mock.calls,
    ]) {
      expect(JSON.stringify(call)).not.toContain("token");
    }
  });
});
