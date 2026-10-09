import { describe, expect, it, vi } from "vitest";
import { makePost } from "@/features/posts/test-helpers";
import { fetchPublicPost, SSR_FETCH_TIMEOUT_MS } from "./server";

const ID = "11111111-1111-4111-8111-111111111111";

function respond(status: number, body: unknown = {}) {
  return vi.fn(async () => new Response(JSON.stringify(body), { status }));
}

describe("fetchPublicPost", () => {
  it("reads the post anonymously and uncached from the backend origin", async () => {
    const post = makePost({ id: ID });
    const fetchImpl = respond(200, post);
    const result = await fetchPublicPost(ID, {
      backendOrigin: "http://127.0.0.1:8000",
      fetchImpl,
    });
    expect(result).toEqual({ kind: "found", post });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`http://127.0.0.1:8000/api/v1/posts/${ID}/`);
    expect(init.cache).toBe("no-store");
    expect(init.signal).toBeInstanceOf(AbortSignal);
    const headers = new Headers(init.headers);
    expect([...headers.keys()]).toEqual(["accept"]); // no token, cookie or secret
  });

  it("is a 404 only when the backend says so", async () => {
    const options = { backendOrigin: "http://127.0.0.1:8000" };
    expect(await fetchPublicPost(ID, { ...options, fetchImpl: respond(404) })).toEqual({
      kind: "not-found",
    });
    for (const status of [500, 502, 503, 401]) {
      expect(await fetchPublicPost(ID, { ...options, fetchImpl: respond(status) })).toEqual({
        kind: "unavailable",
      });
    }
  });

  it("is unavailable, never an exception, when the backend can't be reached or answers oddly", async () => {
    const options = { backendOrigin: "http://127.0.0.1:8000" };
    const down = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    expect(await fetchPublicPost(ID, { ...options, fetchImpl: down })).toEqual({
      kind: "unavailable",
    });
    expect(await fetchPublicPost(ID, { ...options, fetchImpl: respond(200, { id: ID }) })).toEqual({
      kind: "unavailable",
    });
    const html = vi.fn(async () => new Response("<html>", { status: 200 }));
    expect(await fetchPublicPost(ID, { ...options, fetchImpl: html })).toEqual({
      kind: "unavailable",
    });
  });

  it("makes no request when BACKEND_ORIGIN is missing or unsafe", async () => {
    const fetchImpl = respond(200, makePost());
    for (const backendOrigin of ["", "http://api.example.test", "not a url"]) {
      expect(await fetchPublicPost(ID, { backendOrigin, fetchImpl })).toEqual({
        kind: "unavailable",
      });
    }
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("gives up after a few seconds, not a minute", async () => {
    expect(SSR_FETCH_TIMEOUT_MS).toBeLessThanOrEqual(5_000);
    const slow = vi.fn(
      (_url: unknown, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("t", "TimeoutError")),
          );
        }),
    );
    const result = await fetchPublicPost(ID, {
      backendOrigin: "http://127.0.0.1:8000",
      fetchImpl: slow as unknown as typeof fetch,
      timeoutMs: 10,
    });
    expect(result).toEqual({ kind: "unavailable" });
  });

  it("encodes the id into the path", async () => {
    const fetchImpl = respond(404);
    await fetchPublicPost("a/b?c", { backendOrigin: "http://127.0.0.1:8000", fetchImpl });
    expect((fetchImpl.mock.calls[0] as unknown as [string])[0]).toBe(
      "http://127.0.0.1:8000/api/v1/posts/a%2Fb%3Fc/",
    );
  });
});
