"use client";

import { useEffect, useState } from "react";
import type { TrendPoint } from "@/lib/api/types";
import { fetchReputation } from "./reputation-api";

export type TrendPhase = "idle" | "loading" | "ready" | "hidden";

/**
 * The 30-day trend of an account (Part 11D). Public, so it needs no session. `enabled` is false
 * while the score is hidden (the answer would be null). Failure and null both end as `hidden`: the
 * widget then simply has no chart. Results apply in the request's callbacks, only if not aborted.
 */
export function useReputationTrend(
  username: string,
  enabled: boolean,
): { trend: TrendPoint[] | null; phase: TrendPhase } {
  const [state, setState] = useState<{
    username: string;
    trend: TrendPoint[] | null;
    hidden: boolean;
  }>({ username: "", trend: null, hidden: false });

  useEffect(() => {
    if (!enabled) return;
    const mine = new AbortController();
    fetchReputation(username, mine.signal).then(
      (body) => {
        if (mine.signal.aborted) return;
        setState({ username, trend: body.trend, hidden: body.trend === null });
      },
      () => {
        if (!mine.signal.aborted) setState({ username, trend: null, hidden: true });
      },
    );
    return () => mine.abort();
  }, [username, enabled]);

  if (!enabled) return { trend: null, phase: "idle" };
  if (state.username !== username) return { trend: null, phase: "loading" };
  if (state.hidden || !state.trend) return { trend: null, phase: "hidden" };
  return { trend: state.trend, phase: "ready" };
}
