import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import { fetchMyReputationEvents, fetchReputation } from "./reputation-api";

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  api: { get: vi.fn(), post: vi.fn(), del: vi.fn() },
}));

beforeEach(() => vi.clearAllMocks());

describe("fetchReputation", () => {
  it("reads the public summary without the token", async () => {
    vi.mocked(api.get).mockResolvedValue({ score: 62 });
    const signal = new AbortController().signal;
    expect(await fetchReputation("ada", signal)).toEqual({ score: 62 });
    expect(api.get).toHaveBeenCalledWith("/v1/users/ada/reputation/", { signal, token: false });
  });

  it("encodes the name", async () => {
    await fetchReputation("a/b");
    expect(vi.mocked(api.get).mock.calls[0][0]).toBe("/v1/users/a%2Fb/reputation/");
  });
});

describe("fetchMyReputationEvents", () => {
  it("reads your ledger with the token and unwraps the page", async () => {
    vi.mocked(api.get).mockResolvedValue({ results: [{ id: "e1" }], next_cursor: "abc" });
    const page = await fetchMyReputationEvents(null);
    expect(page).toEqual({ items: [{ id: "e1" }], nextCursor: "abc" });
    expect(api.get).toHaveBeenCalledWith("/v1/me/reputation/events/", { signal: undefined });
  });

  it("sends the cursor", async () => {
    vi.mocked(api.get).mockResolvedValue({ results: [], next_cursor: null });
    await fetchMyReputationEvents("a b");
    expect(vi.mocked(api.get).mock.calls[0][0]).toBe("/v1/me/reputation/events/?cursor=a+b");
  });
});
