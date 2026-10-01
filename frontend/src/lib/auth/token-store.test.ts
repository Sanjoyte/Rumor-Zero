import { afterEach, describe, expect, it, vi } from "vitest";
import { getAccessToken, setAccessToken, subscribeToAccessToken } from "./token-store";

afterEach(() => {
  setAccessToken(null);
  vi.restoreAllMocks();
});

describe("token store (browser)", () => {
  it("keeps the token in memory and notifies subscribers", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToAccessToken(listener);
    setAccessToken("access-1");
    expect(getAccessToken()).toBe("access-1");
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    setAccessToken(null);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });

  it("never writes to web storage or document.cookie", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const before = document.cookie;
    setAccessToken("access-2");
    expect(setItem).not.toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe(before);
  });
});
