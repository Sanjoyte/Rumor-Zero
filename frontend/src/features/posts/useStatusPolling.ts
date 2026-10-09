"use client";

import { useEffect, useRef, useState } from "react";
import type { PostStatusUpdate } from "@/lib/api/types";
import { fetchStatuses as defaultFetchStatuses, MAX_STATUS_IDS } from "./posts-api";
import type { StatusOverlay } from "./status-overlay";

/** The first check comes 10 s after the post appears, then each wait is 1.5 times longer, up to 60 s. */
export const POLL_FIRST_DELAY_MS = 10_000;
export const POLL_MAX_DELAY_MS = 60_000;
export const POLL_BACKOFF = 1.5;
/** Polling stops after this much time with the tab visible (ARCHITECTURE §3). */
export const POLL_BUDGET_MS = 10 * 60_000;

export interface StatusPolling {
  /** The newest status of every polled post that has left `pending` (or changed). */
  updates: StatusOverlay;
  /** Posts the server no longer knows (deleted): hide them. */
  gone: ReadonlySet<string>;
}

export interface StatusPollingOptions {
  /** Replaceable for tests. */
  fetchStatuses?: (ids: string[], signal: AbortSignal) => Promise<PostStatusUpdate[]>;
}

export function pollDelay(attempt: number): number {
  return Math.min(POLL_MAX_DELAY_MS, POLL_FIRST_DELAY_MS * POLL_BACKOFF ** attempt);
}

const EMPTY_GONE: ReadonlySet<string> = new Set();

/**
 * Keeps `pending` badges live (ARCHITECTURE §3, ANALYSIS b-2): asks `GET /posts/status/` for the
 * given ids while the tab is visible, backing off from 10 s to 60 s, and stops after 10 minutes of
 * visible time. A hidden tab makes no request and checks once when it comes back. A post that
 * shows up in `ids` for the first time (one you just made) starts the schedule over. Errors are
 * silent: the next check simply tries again. Pass the posts that were *loaded* as pending; the hook
 * stops asking about each one as soon as its status changes or it disappears.
 */
export function useStatusPolling(
  ids: readonly string[],
  options: StatusPollingOptions = {},
): StatusPolling {
  const [state, setState] = useState<StatusPolling>({ updates: {}, gone: EMPTY_GONE });
  // Ids the poll has already settled (no longer pending) or lost (deleted) drop out by themselves.
  const wanted = ids
    .filter((id) => !state.gone.has(id) && (state.updates[id]?.status ?? "pending") === "pending")
    .slice(0, MAX_STATUS_IDS);
  const key = wanted.join(",");

  const idsRef = useRef<string[]>(wanted);
  const fetchRef = useRef(options.fetchStatuses ?? defaultFetchStatuses);
  const known = useRef(new Set<string>());
  const attempt = useRef(0);
  const spent = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controller = useRef<AbortController | null>(null);
  const scheduleRef = useRef<(delay: number) => void>(() => {});

  useEffect(() => {
    fetchRef.current = options.fetchStatuses ?? defaultFetchStatuses;
  });

  useEffect(() => {
    const visible = () => document.visibilityState !== "hidden";
    const stopTimer = () => {
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = null;
    };
    const stopRequest = () => {
      controller.current?.abort();
      controller.current = null;
    };

    async function poll() {
      const asked = idsRef.current.slice();
      if (asked.length === 0) return;
      const mine = new AbortController();
      controller.current = mine;
      try {
        const results = await fetchRef.current(asked, mine.signal);
        if (mine.signal.aborted) return;
        const seen = new Set(results.map((r) => r.id));
        setState((prev) => {
          let updates = prev.updates;
          for (const result of results) {
            const before = prev.updates[result.id];
            const same =
              before !== undefined &&
              before.status === result.status &&
              before.confidence_score === result.confidence_score &&
              before.verdict_source === result.verdict_source;
            if (same || (before === undefined && result.status === "pending")) continue;
            updates = { ...updates, [result.id]: result };
          }
          const missing = asked.filter((id) => !seen.has(id) && !prev.gone.has(id));
          const gone = missing.length ? new Set([...prev.gone, ...missing]) : prev.gone;
          return updates === prev.updates && gone === prev.gone ? prev : { updates, gone };
        });
      } catch {
        // Silent: the next check tries again. (An abort lands here too.)
      } finally {
        if (controller.current === mine) controller.current = null;
      }
    }

    function schedule(delay: number) {
      stopTimer();
      if (!visible() || idsRef.current.length === 0 || spent.current >= POLL_BUDGET_MS) return;
      timer.current = setTimeout(async () => {
        timer.current = null;
        spent.current += delay;
        attempt.current += 1;
        await poll();
        schedule(pollDelay(attempt.current)); // refuses once the budget is spent
      }, delay);
    }
    scheduleRef.current = schedule;

    function onVisibility() {
      if (!visible()) {
        stopTimer();
        stopRequest();
        return;
      }
      // Back on screen: check now (it costs none of the budget), then carry on.
      if (idsRef.current.length === 0 || spent.current >= POLL_BUDGET_MS) return;
      stopTimer();
      void poll().then(() => schedule(pollDelay(attempt.current)));
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stopTimer();
      stopRequest();
    };
  }, []);

  useEffect(() => {
    idsRef.current = key ? key.split(",") : [];
    if (idsRef.current.length === 0) {
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = null;
      return;
    }
    const fresh = idsRef.current.some((id) => !known.current.has(id));
    for (const id of idsRef.current) known.current.add(id);
    if (fresh) {
      attempt.current = 0;
      spent.current = 0;
      scheduleRef.current(pollDelay(0));
    } else if (timer.current === null && spent.current < POLL_BUDGET_MS) {
      scheduleRef.current(pollDelay(attempt.current));
    }
  }, [key]);

  return state;
}
