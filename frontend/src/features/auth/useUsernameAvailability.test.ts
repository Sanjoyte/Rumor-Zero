import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DEBOUNCE_MS, normalizeUsername, useUsernameAvailability } from "./useUsernameAvailability";

const fetchMock = vi.fn<typeof fetch>();

function answer(body: object, status = 200) {
  return Response.json(body, { status });
}

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function settle(ms = DEBOUNCE_MS) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("useUsernameAvailability", () => {
  it("normalises like the server", () => {
    expect(normalizeUsername("  Ａｄａ_99 ")).toBe("ada_99");
  });

  it("waits 400 ms after the last keystroke, then asks once", async () => {
    fetchMock.mockResolvedValue(
      answer({ username: "ada", available: true, reason: null, message: "Available" }),
    );
    const { result, rerender } = renderHook(({ value }) => useUsernameAvailability(value), {
      initialProps: { value: "ad" },
    });
    rerender({ value: "Ada" });
    expect(result.current.status).toBe("idle");
    await settle(DEBOUNCE_MS - 1);
    expect(fetchMock).not.toHaveBeenCalled();
    await settle(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/v1/auth/username-available/?u=ada");
    expect(result.current).toEqual({ status: "available", username: "ada", message: null });
  });

  it("checks the format first, without a request", async () => {
    const { result } = renderHook(() => useUsernameAvailability("ada-lovelace"));
    expect(result.current.status).toBe("invalid");
    expect(result.current.message).toMatch(/3–30 characters/);
    await settle();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("is idle for an empty value", () => {
    const { result } = renderHook(() => useUsernameAvailability("   "));
    expect(result.current.status).toBe("idle");
  });

  it.each([
    ["taken", "That username is taken."],
    ["reserved", "This username is reserved."],
  ])("reports %s", async (reason, message) => {
    fetchMock.mockResolvedValue(answer({ username: "admin", available: false, reason, message }));
    const { result } = renderHook(() => useUsernameAvailability("admin"));
    await settle();
    expect(result.current).toEqual({ status: reason, username: "admin", message });
  });

  it("shows checking while the request runs", async () => {
    let release!: (response: Response) => void;
    fetchMock.mockReturnValue(new Promise((resolve) => (release = resolve)));
    const { result } = renderHook(() => useUsernameAvailability("grace"));
    await settle();
    expect(result.current.status).toBe("checking");
    await act(async () => {
      release(answer({ username: "grace", available: true, reason: null, message: "Available" }));
    });
    expect(result.current.status).toBe("available");
  });

  it("aborts the stale request and never shows its answer", async () => {
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) =>
          (init?.signal as AbortSignal).addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          ),
        ),
    );
    const { result, rerender } = renderHook(({ value }) => useUsernameAvailability(value), {
      initialProps: { value: "first" },
    });
    await settle();
    const firstSignal = fetchMock.mock.calls[0][1]?.signal as AbortSignal;
    fetchMock.mockResolvedValue(
      answer({ username: "second", available: true, reason: null, message: "Available" }),
    );
    rerender({ value: "second" });
    expect(firstSignal.aborted).toBe(true);
    await settle();
    expect(result.current).toEqual({ status: "available", username: "second", message: null });
  });

  it.each([
    [() => Promise.resolve(answer({ detail: "Slow down.", code: "throttled" }, 429))],
    [() => Promise.reject(new TypeError("Failed to fetch"))],
  ])("shows nothing on a 429 or a network error", async (reply) => {
    fetchMock.mockImplementation(reply);
    const { result } = renderHook(() => useUsernameAvailability("ada"));
    await settle();
    expect(result.current.status).toBe("idle");
  });
});
