import { beforeEach, describe, expect, it, vi } from "vitest";

const client = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  api: client,
}));

import {
  fetchNotifications,
  fetchUnreadCount,
  markRead,
  MAX_MARK_READ_IDS,
} from "./notifications-api";

beforeEach(() => {
  client.get.mockReset();
  client.post.mockReset();
});

describe("notifications-api", () => {
  it("reads a page as items and a next cursor", async () => {
    client.get.mockResolvedValue({ results: [1, 2], next_cursor: "c2" });
    const signal = new AbortController().signal;
    expect(await fetchNotifications(null, signal)).toEqual({ items: [1, 2], nextCursor: "c2" });
    expect(client.get).toHaveBeenCalledWith("/v1/notifications/", { signal });
  });

  it("sends the cursor, encoded", async () => {
    client.get.mockResolvedValue({ results: [], next_cursor: null });
    await fetchNotifications("a b/c");
    expect(client.get).toHaveBeenCalledWith("/v1/notifications/?cursor=a+b%2Fc", {
      signal: undefined,
    });
  });

  it("reads the unread count as a number", async () => {
    client.get.mockResolvedValue({ count: 7 });
    const signal = new AbortController().signal;
    expect(await fetchUnreadCount(signal)).toBe(7);
    expect(client.get).toHaveBeenCalledWith("/v1/notifications/unread-count/", { signal });
  });

  it("marks some ids read, or all, and answers the unread count left", async () => {
    client.post.mockResolvedValue({ count: 2 });
    expect(await markRead({ ids: ["a", "b"] })).toBe(2);
    expect(client.post).toHaveBeenLastCalledWith("/v1/notifications/mark-read/", {
      ids: ["a", "b"],
    });
    expect(await markRead({ all: true })).toBe(2);
    expect(client.post).toHaveBeenLastCalledWith("/v1/notifications/mark-read/", { all: true });
  });

  it("knows the server's limit on ids", () => {
    expect(MAX_MARK_READ_IDS).toBe(50);
  });
});
