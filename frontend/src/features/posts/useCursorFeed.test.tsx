import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { type CursorPage, useCursorFeed } from "./useCursorFeed";

interface Item {
  id: string;
}

const item = (id: string): Item => ({ id });
const page = (ids: string[], nextCursor: string | null = null): CursorPage<Item> => ({
  items: ids.map(item),
  nextCursor,
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup(
  fetchPage: (cursor: string | null, signal: AbortSignal) => Promise<CursorPage<Item>>,
  initial: { enabled?: boolean; resetKey?: string | null } = {},
) {
  return renderHook(
    (props: { enabled: boolean; resetKey: string | null }) =>
      useCursorFeed<Item>({ fetchPage, keyOf, ...props }),
    { initialProps: { enabled: initial.enabled ?? true, resetKey: initial.resetKey ?? "u1" } },
  );
}

const ids = (items: Item[]) => items.map((i) => i.id);
const keyOf = (i: Item) => i.id;

describe("useCursorFeed", () => {
  it("does not fetch until it is enabled (the session is still loading)", async () => {
    const fetchPage = vi.fn().mockResolvedValue(page(["a"]));
    const { result, rerender } = setup(fetchPage, { enabled: false });
    expect(fetchPage).not.toHaveBeenCalled();
    expect(result.current.phase).toBe("idle");
    rerender({ enabled: true, resetKey: "u1" });
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    expect(fetchPage).toHaveBeenCalledTimes(1);
    expect(fetchPage).toHaveBeenCalledWith(null, expect.any(AbortSignal));
  });

  it("loads the first page", async () => {
    const { result } = setup(vi.fn().mockResolvedValue(page(["a", "b"], "c1")));
    expect(result.current.phase).toBe("loading");
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    expect(ids(result.current.items)).toEqual(["a", "b"]);
    expect(result.current.hasMore).toBe(true);
  });

  it("appends the next page with the cursor, and stops when there is no cursor", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(["a", "b"], "c1"))
      .mockResolvedValueOnce(page(["c"], null));
    const { result } = setup(fetchPage);
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    act(() => result.current.loadMore());
    await waitFor(() => expect(ids(result.current.items)).toEqual(["a", "b", "c"]));
    expect(fetchPage).toHaveBeenLastCalledWith("c1", expect.any(AbortSignal));
    expect(result.current.hasMore).toBe(false);
    expect(result.current.loadingMore).toBe(false);
  });

  it("loads one page when Load more is clicked twice", async () => {
    const second = deferred<CursorPage<Item>>();
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(["a"], "c1"))
      .mockReturnValueOnce(second.promise);
    const { result } = setup(fetchPage);
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    act(() => {
      result.current.loadMore();
      result.current.loadMore();
    });
    expect(result.current.loadingMore).toBe(true);
    act(() => result.current.loadMore());
    expect(fetchPage).toHaveBeenCalledTimes(2);
    await act(async () => second.resolve(page(["b"])));
    expect(ids(result.current.items)).toEqual(["a", "b"]);
  });

  it("puts a new item at the top and never shows it twice", async () => {
    const { result } = setup(vi.fn().mockResolvedValue(page(["a", "b"], "c1")));
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    act(() => result.current.prepend(item("new")));
    expect(ids(result.current.items)).toEqual(["new", "a", "b"]);
    act(() => result.current.prepend(item("a"))); // already on a loaded page
    expect(ids(result.current.items)).toEqual(["a", "new", "b"]);
    act(() => result.current.prepend(item("new")));
    expect(ids(result.current.items).filter((i) => i === "new")).toHaveLength(1);
  });

  it("keeps an item added while the first page was still loading", async () => {
    const first = deferred<CursorPage<Item>>();
    const { result } = setup(vi.fn().mockReturnValue(first.promise));
    act(() => result.current.prepend(item("mine")));
    expect(ids(result.current.items)).toEqual(["mine"]);
    await act(async () => first.resolve(page(["a", "b"])));
    expect(ids(result.current.items)).toEqual(["mine", "a", "b"]);
  });

  it("drops the duplicate when the server's first page already has the new item", async () => {
    const first = deferred<CursorPage<Item>>();
    const { result } = setup(vi.fn().mockReturnValue(first.promise));
    act(() => result.current.prepend(item("mine")));
    await act(async () => first.resolve(page(["mine", "a"])));
    expect(ids(result.current.items)).toEqual(["mine", "a"]);
  });

  it("reports a failed first page and retries from the top", async () => {
    const boom = new ApiError({ status: 503, code: "backend_waking", detail: "waking" });
    const fetchPage = vi
      .fn()
      .mockRejectedValueOnce(boom)
      .mockResolvedValueOnce(page(["a"]));
    const { result } = setup(fetchPage);
    await waitFor(() => expect(result.current.phase).toBe("error"));
    expect(result.current.error).toBe(boom);
    expect(result.current.items).toEqual([]);
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    expect(ids(result.current.items)).toEqual(["a"]);
    expect(result.current.error).toBeNull();
  });

  it("keeps the list when Load more fails, and the next try works", async () => {
    const boom = new ApiError({ status: 0, code: "network_error", detail: "offline" });
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(["a"], "c1"))
      .mockRejectedValueOnce(boom)
      .mockResolvedValueOnce(page(["b"]));
    const { result } = setup(fetchPage);
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.moreError).toBe(boom));
    expect(ids(result.current.items)).toEqual(["a"]);
    expect(result.current.hasMore).toBe(true);
    act(() => result.current.loadMore());
    await waitFor(() => expect(ids(result.current.items)).toEqual(["a", "b"]));
    expect(result.current.moreError).toBeNull();
  });

  it("starts again from the top when the cursor is rejected with a 404", async () => {
    const gone = new ApiError({ status: 404, code: "not_found", detail: "Invalid cursor." });
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(["a"], "stale"))
      .mockRejectedValueOnce(gone)
      .mockResolvedValueOnce(page(["fresh"]));
    const { result } = setup(fetchPage);
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    act(() => result.current.loadMore());
    await waitFor(() => expect(ids(result.current.items)).toEqual(["fresh"]));
    expect(fetchPage).toHaveBeenLastCalledWith(null, expect.any(AbortSignal));
  });

  it("reloads from the top when the user changes, and forgets what they added", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(["a"]))
      .mockResolvedValueOnce(page(["b"]));
    const { result, rerender } = setup(fetchPage, { resetKey: "u1" });
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    act(() => result.current.prepend(item("mine")));
    rerender({ enabled: true, resetKey: "u2" });
    await waitFor(() => expect(ids(result.current.items)).toEqual(["b"]));
  });

  it("ignores a response that arrives after the user changed", async () => {
    const stale = deferred<CursorPage<Item>>();
    const fetchPage = vi
      .fn()
      .mockReturnValueOnce(stale.promise)
      .mockResolvedValueOnce(page(["new-user"]));
    const { result, rerender } = setup(fetchPage, { resetKey: "u1" });
    rerender({ enabled: true, resetKey: "u2" });
    await waitFor(() => expect(ids(result.current.items)).toEqual(["new-user"]));
    await act(async () => stale.resolve(page(["old-user"])));
    expect(ids(result.current.items)).toEqual(["new-user"]);
  });

  it("aborts the request when it unmounts", async () => {
    let signal: AbortSignal | undefined;
    const fetchPage = vi.fn((_cursor: string | null, s: AbortSignal) => {
      signal = s;
      return new Promise<CursorPage<Item>>(() => {});
    });
    const { unmount } = setup(fetchPage);
    expect(signal?.aborted).toBe(false);
    unmount();
    expect(signal?.aborted).toBe(true);
  });

  it("does not report an aborted first page as an error", async () => {
    const abort = new DOMException("Aborted", "AbortError");
    const fetchPage = vi
      .fn()
      .mockImplementationOnce(
        (_c: string | null, s: AbortSignal) =>
          new Promise((_, reject) => s.addEventListener("abort", () => reject(abort))),
      )
      .mockResolvedValueOnce(page(["a"]));
    const { result, rerender } = setup(fetchPage, { resetKey: "u1" });
    rerender({ enabled: true, resetKey: "u2" });
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    expect(result.current.error).toBeNull();
  });
});
