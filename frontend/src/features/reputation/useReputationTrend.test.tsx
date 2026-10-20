import { renderHook, waitFor } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { makeSummary, makeTrend } from "./test-helpers";
import { useReputationTrend } from "./useReputationTrend";

const api = vi.hoisted(() => ({ fetchReputation: vi.fn() }));
vi.mock("./reputation-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./reputation-api")>()),
  ...api,
}));

beforeEach(() => vi.clearAllMocks());

describe("useReputationTrend", () => {
  it("does not fetch while the score is hidden", () => {
    const { result } = renderHook(() => useReputationTrend("bob", false));
    expect(result.current).toEqual({ trend: null, phase: "idle" });
    expect(api.fetchReputation).not.toHaveBeenCalled();
  });

  it("loads, then returns the points", async () => {
    api.fetchReputation.mockResolvedValue(makeSummary());
    const { result } = renderHook(() => useReputationTrend("bob", true));
    expect(result.current.phase).toBe("loading");
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    expect(result.current.trend).toHaveLength(30);
    expect(api.fetchReputation).toHaveBeenCalledWith("bob", expect.any(AbortSignal));
  });

  it("hides the chart when the answer has no trend", async () => {
    api.fetchReputation.mockResolvedValue(makeSummary({ trend: null }));
    const { result } = renderHook(() => useReputationTrend("bob", true));
    await waitFor(() => expect(result.current.phase).toBe("hidden"));
    expect(result.current.trend).toBeNull();
  });

  it("hides the chart when the request fails", async () => {
    api.fetchReputation.mockRejectedValue(new Error("down"));
    const { result } = renderHook(() => useReputationTrend("bob", true));
    await waitFor(() => expect(result.current.phase).toBe("hidden"));
  });

  it("works under StrictMode", async () => {
    api.fetchReputation.mockResolvedValue(makeSummary());
    const wrapper = ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>;
    const { result } = renderHook(() => useReputationTrend("bob", true), { wrapper });
    await waitFor(() => expect(result.current.phase).toBe("ready"));
  });

  it("goes back to loading for another account and never shows the old line", async () => {
    api.fetchReputation.mockResolvedValueOnce(makeSummary({ trend: makeTrend(10, 20) }));
    const { result, rerender } = renderHook(({ name }) => useReputationTrend(name, true), {
      initialProps: { name: "bob" },
    });
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    api.fetchReputation.mockReturnValueOnce(new Promise(() => {}));
    rerender({ name: "cy" });
    expect(result.current).toEqual({ trend: null, phase: "loading" });
  });

  it("ignores an answer that arrives after the account changed", async () => {
    let first: (value: unknown) => void = () => {};
    api.fetchReputation.mockReturnValueOnce(new Promise((r) => (first = r)));
    api.fetchReputation.mockResolvedValueOnce(makeSummary({ trend: makeTrend(40, 41) }));
    const { result, rerender } = renderHook(({ name }) => useReputationTrend(name, true), {
      initialProps: { name: "bob" },
    });
    rerender({ name: "cy" });
    await waitFor(() => expect(result.current.phase).toBe("ready"));
    first(makeSummary({ trend: makeTrend(90, 91) }));
    await Promise.resolve();
    expect(result.current.trend?.[0].score).toBe(40);
  });
});
