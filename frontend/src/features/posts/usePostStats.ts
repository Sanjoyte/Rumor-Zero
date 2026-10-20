"use client";

import { useEffect, useState } from "react";
import type { Post, PostStats } from "@/lib/api/types";
import { fetchPostStats } from "./posts-api";

export type StatsPhase = "loading" | "ready" | "error";

/**
 * The stats of a post (Part 11D). Public, so there is no session to wait for. It fetches on mount
 * and again whenever the label changes (the live badge flip), keeping the numbers it already has
 * while the new ones load. A failure with nothing to show is `error`, which the section hides.
 * (The result is applied in the request's callbacks and only if it wasn't aborted: StrictMode runs
 * effect, cleanup, effect on mount.)
 */
export function usePostStats(
  id: string,
  label: Pick<Post, "status" | "verdict_source" | "confidence_score">,
): { stats: PostStats | null; phase: StatsPhase } {
  const [state, setState] = useState<{ stats: PostStats | null; phase: StatsPhase }>({
    stats: null,
    phase: "loading",
  });
  const labelKey = `${label.status}|${label.verdict_source ?? ""}|${label.confidence_score ?? ""}`;

  useEffect(() => {
    const mine = new AbortController();
    fetchPostStats(id, mine.signal).then(
      (stats) => {
        if (!mine.signal.aborted) setState({ stats, phase: "ready" });
      },
      () => {
        if (!mine.signal.aborted) {
          setState((prev) => (prev.stats ? prev : { stats: null, phase: "error" }));
        }
      },
    );
    return () => mine.abort();
  }, [id, labelKey]);

  return state;
}
