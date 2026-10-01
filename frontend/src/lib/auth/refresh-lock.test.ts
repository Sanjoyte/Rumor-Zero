import { afterEach, describe, expect, it, vi } from "vitest";
import { REFRESH_LOCK_NAME, withRefreshLock } from "./refresh-lock";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((r) => (resolve = r));
  return { promise, resolve };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("withRefreshLock", () => {
  it("uses navigator.locks with the rz-refresh lock when available", async () => {
    const request = vi.fn((_name: string, callback: () => Promise<unknown>) => callback());
    vi.stubGlobal("navigator", { locks: { request } });
    expect(await withRefreshLock(async () => "token")).toBe("token");
    expect(request).toHaveBeenCalledWith(REFRESH_LOCK_NAME, expect.any(Function));
  });

  it("serialises tasks in the tab when Web Locks are missing", async () => {
    vi.stubGlobal("navigator", {});
    const order: string[] = [];
    const gate = deferred();
    const first = withRefreshLock(async () => {
      order.push("first:start");
      await gate.promise;
      order.push("first:end");
      return 1;
    });
    const second = withRefreshLock(async () => {
      order.push("second:start");
      return 2;
    });
    await Promise.resolve();
    expect(order).toEqual(["first:start"]);
    gate.resolve();
    expect(await Promise.all([first, second])).toEqual([1, 2]);
    expect(order).toEqual(["first:start", "first:end", "second:start"]);
  });

  it("keeps the queue going after a failed task", async () => {
    vi.stubGlobal("navigator", {});
    await expect(
      withRefreshLock(async () => Promise.reject(new Error("refresh failed"))),
    ).rejects.toThrow("refresh failed");
    expect(await withRefreshLock(async () => "next")).toBe("next");
  });
});
