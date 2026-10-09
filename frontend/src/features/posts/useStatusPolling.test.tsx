import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import type { PostStatusUpdate } from "@/lib/api/types";
import {
  POLL_BACKOFF,
  POLL_BUDGET_MS,
  POLL_FIRST_DELAY_MS,
  POLL_MAX_DELAY_MS,
  pollDelay,
  useStatusPolling,
} from "./useStatusPolling";

const pending = (id: string): PostStatusUpdate => ({
  id,
  status: "pending",
  confidence_score: null,
  verdict_source: null,
});
const verified = (id: string): PostStatusUpdate => ({
  id,
  status: "verified_true",
  confidence_score: "94.00",
  verdict_source: "pipeline",
});

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

function setup(
  initial: string[],
  fetchStatuses: Mock<(ids: string[], signal: AbortSignal) => Promise<PostStatusUpdate[]>> = vi.fn(
    async (ids: string[]) => ids.map(pending),
  ),
) {
  const view = renderHook(({ ids }) => useStatusPolling(ids, { fetchStatuses }), {
    initialProps: { ids: initial },
  });
  return { ...view, fetchStatuses };
}

describe("pollDelay", () => {
  it("starts at 10 s, grows by half each time and stops at 60 s", () => {
    expect([0, 1, 2, 3, 4, 5, 6, 20].map(pollDelay)).toEqual([
      10_000, 15_000, 22_500, 33_750, 50_625, 60_000, 60_000, 60_000,
    ]);
    expect([POLL_FIRST_DELAY_MS, POLL_BACKOFF, POLL_MAX_DELAY_MS, POLL_BUDGET_MS]).toEqual([
      10_000, 1.5, 60_000, 600_000,
    ]);
  });
});

describe("useStatusPolling", () => {
  it("asks nothing for an empty list", async () => {
    const { fetchStatuses } = setup([]);
    await tick(5 * 60_000);
    expect(fetchStatuses).not.toHaveBeenCalled();
  });

  it("makes the first check after 10 s and not before", async () => {
    const { fetchStatuses } = setup(["a", "b"]);
    await tick(9_999);
    expect(fetchStatuses).not.toHaveBeenCalled();
    await tick(1);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
    expect(fetchStatuses).toHaveBeenCalledWith(["a", "b"], expect.any(AbortSignal));
  });

  it("backs off: 10 s, then 15 s, then 22.5 s", async () => {
    const { fetchStatuses } = setup(["a"]);
    await tick(10_000);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
    await tick(14_999);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
    await tick(1);
    expect(fetchStatuses).toHaveBeenCalledTimes(2);
    await tick(22_499);
    expect(fetchStatuses).toHaveBeenCalledTimes(2);
    await tick(1);
    expect(fetchStatuses).toHaveBeenCalledTimes(3);
  });

  it("reports a post that left pending, and stops asking about it", async () => {
    const fetchStatuses = vi.fn(async (ids: string[]) =>
      ids.map((id) => (id === "a" ? verified(id) : pending(id))),
    );
    const { result } = setup(["a", "b"], fetchStatuses);
    await tick(10_000);
    expect(result.current.updates).toEqual({ a: verified("a") });
    expect(result.current.updates.b).toBeUndefined(); // still pending: nothing to overlay
    await tick(15_000);
    expect(fetchStatuses).toHaveBeenLastCalledWith(["b"], expect.any(AbortSignal));
  });

  it("stops entirely once nothing is pending", async () => {
    const { fetchStatuses } = setup(
      ["a"],
      vi.fn(async () => [verified("a")]),
    );
    await tick(10_000);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
    await tick(10 * 60_000);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
  });

  it("reports a post the server no longer knows as gone, and stops asking about it", async () => {
    const fetchStatuses = vi.fn(async () => [] as PostStatusUpdate[]);
    const { result } = setup(["a"], fetchStatuses);
    await tick(10_000);
    expect([...result.current.gone]).toEqual(["a"]);
    await tick(5 * 60_000);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
  });

  it("makes no request while the tab is hidden, and checks once when it returns", async () => {
    const { fetchStatuses } = setup(["a"]);
    await tick(5_000);
    act(() => setVisibility("hidden"));
    await tick(5 * 60_000);
    expect(fetchStatuses).not.toHaveBeenCalled();
    await act(async () => setVisibility("visible"));
    await tick(0);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
  });

  it("starts nothing when the page opens in a hidden tab", async () => {
    visibility = "hidden";
    const { fetchStatuses } = setup(["a"]);
    await tick(60_000);
    expect(fetchStatuses).not.toHaveBeenCalled();
    await act(async () => setVisibility("visible"));
    await tick(0);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
  });

  it("stops after 10 minutes of visible time", async () => {
    const { fetchStatuses } = setup(["a"]);
    await tick(POLL_BUDGET_MS + 60_000);
    const calls = fetchStatuses.mock.calls.length;
    expect(calls).toBeGreaterThan(5);
    expect(calls).toBeLessThan(20);
    await tick(60 * 60_000);
    expect(fetchStatuses).toHaveBeenCalledTimes(calls);
  });

  it("doesn't spend the budget while hidden", async () => {
    const { fetchStatuses } = setup(["a"]);
    await tick(POLL_BUDGET_MS / 2);
    const before = fetchStatuses.mock.calls.length;
    act(() => setVisibility("hidden"));
    await tick(2 * 60 * 60_000); // two hours away
    await act(async () => setVisibility("visible"));
    await tick(POLL_BUDGET_MS / 4);
    expect(fetchStatuses.mock.calls.length).toBeGreaterThan(before + 1);
  });

  it("starts the schedule over when a new post appears", async () => {
    const { rerender, fetchStatuses } = setup(["a"]);
    await tick(POLL_BUDGET_MS + 60_000); // the first one's budget is spent
    const spent = fetchStatuses.mock.calls.length;
    rerender({ ids: ["a", "new"] });
    await tick(9_999);
    expect(fetchStatuses).toHaveBeenCalledTimes(spent);
    await tick(1);
    expect(fetchStatuses).toHaveBeenCalledTimes(spent + 1);
    expect(fetchStatuses).toHaveBeenLastCalledWith(["a", "new"], expect.any(AbortSignal));
  });

  it("doesn't restart for the same ids or for fewer ids", async () => {
    const { rerender, fetchStatuses } = setup(["a", "b"]);
    await tick(10_000);
    rerender({ ids: ["a", "b"] });
    rerender({ ids: ["a"] });
    await tick(14_999);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
    await tick(1);
    expect(fetchStatuses).toHaveBeenCalledTimes(2);
  });

  it("asks about at most 50 posts", async () => {
    const ids = Array.from({ length: 60 }, (_, i) => `p${i}`);
    const { fetchStatuses } = setup(ids);
    await tick(10_000);
    expect((fetchStatuses.mock.calls[0] as unknown as [string[]])[0]).toHaveLength(50);
  });

  it("stays silent on errors and tries again", async () => {
    const fetchStatuses = vi
      .fn<(ids: string[]) => Promise<PostStatusUpdate[]>>()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue([verified("a")]);
    const { result } = setup(["a"], fetchStatuses);
    await tick(10_000);
    expect(result.current.updates).toEqual({});
    await tick(15_000);
    expect(result.current.updates).toEqual({ a: verified("a") });
  });

  it("aborts the request in flight and cancels the timer on unmount", async () => {
    let signal: AbortSignal | undefined;
    const fetchStatuses = vi.fn(
      (_ids: string[], s: AbortSignal) =>
        new Promise<PostStatusUpdate[]>(() => {
          signal = s;
        }),
    );
    const { unmount } = setup(["a"], fetchStatuses);
    await tick(10_000);
    expect(signal?.aborted).toBe(false);
    unmount();
    expect(signal?.aborted).toBe(true);
    await tick(10 * 60_000);
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
  });

  it("ignores an answer that arrives after the tab was hidden", async () => {
    let resolve: (value: PostStatusUpdate[]) => void = () => {};
    const fetchStatuses = vi.fn(() => new Promise<PostStatusUpdate[]>((r) => (resolve = r)));
    const { result } = setup(["a"], fetchStatuses);
    await tick(10_000);
    act(() => setVisibility("hidden"));
    await act(async () => resolve([verified("a")]));
    expect(result.current.updates).toEqual({});
  });
});
