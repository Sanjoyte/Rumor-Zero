import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { sessionOf, VERIFIED_ME } from "@/features/posts/test-helpers";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { NOTIFICATION_POLL_MS, UnreadCountProvider, useUnreadCount } from "./UnreadCountProvider";

let visibility: "visible" | "hidden" = "visible";
function setVisibility(value: "visible" | "hidden") {
  visibility = value;
  document.dispatchEvent(new Event("visibilitychange"));
}

beforeEach(() => {
  vi.useFakeTimers();
  visibility = "visible";
  vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const tick = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

type Fetch = (signal: AbortSignal) => Promise<number>;

function setup(fetchCount: Fetch, kind: "verified" | "anonymous" | "loading" = "verified") {
  const session = sessionOf(kind);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <AuthProvider session={session.session}>
      <UnreadCountProvider fetchCount={fetchCount}>{children}</UnreadCountProvider>
    </AuthProvider>
  );
  return { ...renderHook(() => useUnreadCount(), { wrapper }), session };
}

const answering = (...counts: number[]) => {
  let n = 0;
  return vi.fn<Fetch>(async () => counts[Math.min(n++, counts.length - 1)]);
};

describe("UnreadCountProvider", () => {
  it("polls every 30 seconds", () => {
    expect(NOTIFICATION_POLL_MS).toBe(30_000);
  });

  it("asks at once when a signed-in session is ready, then every 30 s", async () => {
    const fetchCount = answering(3);
    const { result } = setup(fetchCount);
    await tick(0);
    expect(fetchCount).toHaveBeenCalledTimes(1);
    expect(result.current.count).toBe(3);
    await tick(29_999);
    expect(fetchCount).toHaveBeenCalledTimes(1);
    await tick(1);
    expect(fetchCount).toHaveBeenCalledTimes(2);
    await tick(30_000);
    expect(fetchCount).toHaveBeenCalledTimes(3);
  });

  it("asks nothing and shows 0 for a visitor", async () => {
    const fetchCount = answering(3);
    const { result } = setup(fetchCount, "anonymous");
    await tick(5 * 60_000);
    expect(fetchCount).not.toHaveBeenCalled();
    expect(result.current.count).toBe(0);
  });

  it("waits for the session before asking", async () => {
    const fetchCount = answering(3);
    setup(fetchCount, "loading");
    await tick(60_000);
    expect(fetchCount).not.toHaveBeenCalled();
  });

  it("is 0 outside a provider", () => {
    const { result } = renderHook(() => useUnreadCount());
    expect(result.current.count).toBe(0);
    expect(() => result.current.set(5)).not.toThrow();
  });

  it("makes no request on a hidden tab, and none starts when it is hidden at mount", async () => {
    visibility = "hidden";
    const fetchCount = answering(3);
    setup(fetchCount);
    await tick(5 * 60_000);
    expect(fetchCount).not.toHaveBeenCalled();
  });

  it("stops the timer when the tab is hidden and asks at once when it comes back", async () => {
    const fetchCount = answering(1, 2);
    const { result } = setup(fetchCount);
    await tick(0);
    expect(fetchCount).toHaveBeenCalledTimes(1);
    act(() => setVisibility("hidden"));
    await tick(5 * 60_000);
    expect(fetchCount).toHaveBeenCalledTimes(1);
    act(() => setVisibility("visible"));
    await tick(0);
    expect(fetchCount).toHaveBeenCalledTimes(2);
    expect(result.current.count).toBe(2);
    await tick(30_000);
    expect(fetchCount).toHaveBeenCalledTimes(3);
  });

  it("aborts the request in flight when the tab is hidden, and ignores its answer", async () => {
    let seen: AbortSignal | null = null;
    let resolve: (n: number) => void = () => {};
    const fetchCount = vi.fn<Fetch>((signal) => {
      seen = signal;
      return new Promise<number>((r) => (resolve = r));
    });
    const { result } = setup(fetchCount);
    await tick(0);
    act(() => setVisibility("hidden"));
    expect(seen).not.toBeNull();
    expect((seen as unknown as AbortSignal).aborted).toBe(true);
    await act(async () => resolve(9));
    expect(result.current.count).toBe(0);
  });

  it("stops everything on unmount", async () => {
    const fetchCount = answering(1);
    const view = setup(fetchCount);
    await tick(0);
    view.unmount();
    await tick(5 * 60_000);
    expect(fetchCount).toHaveBeenCalledTimes(1);
  });

  it("keeps the last count when a request fails", async () => {
    const fetchCount = vi
      .fn<Fetch>()
      .mockResolvedValueOnce(4)
      .mockRejectedValueOnce(new Error("down"))
      .mockResolvedValue(5);
    const { result } = setup(fetchCount);
    await tick(0);
    expect(result.current.count).toBe(4);
    await tick(30_000);
    expect(result.current.count).toBe(4);
    await tick(30_000);
    expect(result.current.count).toBe(5);
  });

  describe("arrivals", () => {
    it("does not count the first answer", async () => {
      const { result } = setup(answering(5));
      await tick(0);
      expect(result.current.count).toBe(5);
      expect(result.current.arrivals).toBe(0);
    });

    it("counts a rise, not a fall or the same number", async () => {
      const { result } = setup(answering(2, 2, 4, 1));
      await tick(0);
      await tick(30_000);
      expect(result.current.arrivals).toBe(0);
      await tick(30_000);
      expect(result.current.arrivals).toBe(1);
      await tick(30_000);
      expect(result.current.count).toBe(1);
      expect(result.current.arrivals).toBe(1);
    });

    it("counts a rise from 0", async () => {
      const { result } = setup(answering(0, 1));
      await tick(0);
      await tick(30_000);
      expect(result.current.arrivals).toBe(1);
    });
  });

  describe("local changes", () => {
    it("set() uses the server's number and never goes below 0", async () => {
      const { result } = setup(answering(5));
      await tick(0);
      act(() => result.current.set(2));
      expect(result.current.count).toBe(2);
      act(() => result.current.set(-4));
      expect(result.current.count).toBe(0);
    });

    it("adjust() moves the number and never goes below 0", async () => {
      const { result } = setup(answering(2));
      await tick(0);
      act(() => result.current.adjust(-1));
      expect(result.current.count).toBe(1);
      act(() => result.current.adjust(-5));
      expect(result.current.count).toBe(0);
      act(() => result.current.adjust(3));
      expect(result.current.count).toBe(3);
    });

    it("drops a poll that started before a local change", async () => {
      let resolve: (n: number) => void = () => {};
      const fetchCount = vi
        .fn<Fetch>()
        .mockResolvedValueOnce(2)
        .mockImplementationOnce(() => new Promise<number>((r) => (resolve = r)));
      const { result } = setup(fetchCount);
      await tick(0);
      await tick(30_000); // the second request is now in flight
      act(() => result.current.adjust(-1)); // the person marks one read
      expect(result.current.count).toBe(1);
      await act(async () => resolve(2)); // the older answer lands: stale, ignored
      expect(result.current.count).toBe(1);
      expect(result.current.arrivals).toBe(0);
    });

    it("drops a poll that started before a set() too (the mark-read answer is the newer truth)", async () => {
      let resolve: (n: number) => void = () => {};
      const fetchCount = vi
        .fn<Fetch>()
        .mockResolvedValueOnce(5)
        .mockImplementationOnce(() => new Promise<number>((r) => (resolve = r)));
      const { result } = setup(fetchCount);
      await tick(0);
      await tick(30_000); // in flight
      act(() => result.current.set(1)); // the server said 1 after a mark-read
      await act(async () => resolve(5)); // the older answer says 5
      expect(result.current.count).toBe(1);
      expect(result.current.arrivals).toBe(0);
    });

    it("accepts a poll that started after the change", async () => {
      const { result } = setup(answering(2, 7));
      await tick(0);
      act(() => result.current.adjust(-1));
      await tick(30_000);
      expect(result.current.count).toBe(7);
      expect(result.current.arrivals).toBe(1);
    });
  });

  it("starts from nothing for another person, not with the last person's count", async () => {
    const answers = [Promise.resolve(6), new Promise<number>(() => {})];
    const fetchCount = vi.fn<Fetch>(() => answers.shift() ?? new Promise<number>(() => {}));
    const { result, session } = setup(fetchCount);
    await tick(0);
    expect(result.current.count).toBe(6);
    await act(async () => {
      await session.session.logout();
    });
    expect(result.current.count).toBe(0);
    session.api.fetchMe.mockResolvedValue({ ...VERIFIED_ME, id: "u-9", username: "cy" });
    await act(async () => {
      await session.session.login("cy@example.test", "pw");
    });
    await tick(0);
    expect(fetchCount).toHaveBeenCalledTimes(2);
    expect(result.current.count).toBe(0); // their own answer hasn't come yet
  });
});
