"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fetchUnreadCount as defaultFetchUnreadCount } from "./notifications-api";

/** How often the unread count is asked for while the tab is visible (ARCHITECTURE §3). */
export const NOTIFICATION_POLL_MS = 30_000;

export interface UnreadCount {
  /** The number of unread notifications; 0 until the first answer and when signed out. */
  count: number;
  /**
   * Goes up by one each time a poll finds more unread items than it knew of before: the open
   * `/notifications` page reloads its first page then. The first answer never counts.
   */
  arrivals: number;
  /** Use the server's number (the answer to a mark-read). */
  set: (count: number) => void;
  /** Change the number now, before the server's answer (a click that marks one item read). */
  adjust: (delta: number) => void;
}

const NONE: UnreadCount = { count: 0, arrivals: 0, set: () => {}, adjust: () => {} };
const UnreadCountContext = createContext<UnreadCount>(NONE);

/** The unread count for the shell's badge and the notifications page. Outside a provider it is 0. */
export function useUnreadCount(): UnreadCount {
  return useContext(UnreadCountContext);
}

interface State {
  /** null until the first answer. */
  count: number | null;
  arrivals: number;
}

const INITIAL: State = { count: null, arrivals: 0 };

export interface UnreadCountProviderProps {
  children: ReactNode;
  /** Replaceable for tests. */
  fetchCount?: (signal: AbortSignal) => Promise<number>;
  intervalMs?: number;
}

/**
 * Polls `GET /notifications/unread-count/` every 30 s **while the tab is visible** (user decision:
 * guide §11). It asks at once when it mounts signed in and when the tab comes back; a hidden tab
 * stops the timer and aborts the request in flight. Errors are silent: the last count stays and the
 * next tick tries again. A poll that started before a local change (`set`, `adjust`) is dropped
 * when it lands, so a stale answer can neither undo the change nor look like a new arrival.
 */
export function UnreadCountProvider({
  children,
  fetchCount,
  intervalMs = NOTIFICATION_POLL_MS,
}: UnreadCountProviderProps) {
  const { status, user } = useAuth();
  const userId = user?.id ?? null;
  const authenticated = status === "authenticated" && userId !== null;
  const [state, setState] = useState<State>(INITIAL);
  // A different person (log out, log in as someone else) starts from nothing.
  const [owner, setOwner] = useState<string | null>(userId);
  if (owner !== userId) {
    setOwner(userId);
    setState(INITIAL);
  }

  const version = useRef(0);
  const fetchRef = useRef(fetchCount ?? defaultFetchUnreadCount);
  useEffect(() => {
    fetchRef.current = fetchCount ?? defaultFetchUnreadCount;
  });

  useEffect(() => {
    if (!authenticated) return;
    let timer: ReturnType<typeof setInterval> | null = null;
    let controller: AbortController | null = null;
    const visible = () => document.visibilityState !== "hidden";
    const stopTimer = () => {
      if (timer !== null) clearInterval(timer);
      timer = null;
    };
    const stopRequest = () => {
      controller?.abort();
      controller = null;
    };

    async function poll() {
      stopRequest();
      const mine = new AbortController();
      controller = mine;
      const started = version.current;
      try {
        const count = await fetchRef.current(mine.signal);
        if (mine.signal.aborted || started !== version.current) return;
        setState((prev) => ({
          count,
          arrivals: prev.count !== null && count > prev.count ? prev.arrivals + 1 : prev.arrivals,
        }));
      } catch {
        // Silent: the last count stays and the next tick tries again. (An abort lands here too.)
      } finally {
        if (controller === mine) controller = null;
      }
    }

    function start() {
      stopTimer();
      void poll();
      timer = setInterval(() => void poll(), intervalMs);
    }
    function onVisibility() {
      if (visible()) {
        start();
      } else {
        stopTimer();
        stopRequest();
      }
    }

    if (visible()) start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stopTimer();
      stopRequest();
    };
  }, [authenticated, userId, intervalMs]);

  const set = useCallback((count: number) => {
    version.current += 1;
    setState((prev) => ({ ...prev, count: Math.max(0, count) }));
  }, []);
  const adjust = useCallback((delta: number) => {
    version.current += 1;
    setState((prev) => ({ ...prev, count: Math.max(0, (prev.count ?? 0) + delta) }));
  }, []);

  // A visitor's state is always the initial one (a change of person resets it above).
  const count = state.count ?? 0;
  const arrivals = state.arrivals;
  const value = useMemo(() => ({ count, arrivals, set, adjust }), [count, arrivals, set, adjust]);
  return <UnreadCountContext.Provider value={value}>{children}</UnreadCountContext.Provider>;
}
