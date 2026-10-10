"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";

export interface CursorPage<T> {
  items: T[];
  nextCursor: string | null;
}

export interface UseCursorFeedOptions<T> {
  /** Fetch one page; `cursor` is null for the first. Must honour `signal`. */
  fetchPage: (cursor: string | null, signal: AbortSignal) => Promise<CursorPage<T>>;
  /** Must be a stable function (declared outside the component, or memoised). */
  keyOf: (item: T) => string;
  /** False while the session is still loading: a first request would go out without a token. */
  enabled: boolean;
  /** Reload from the top when this changes (the signed-in user id). */
  resetKey: string | null;
}

export type FeedPhase = "idle" | "loading" | "ready" | "error";

export interface CursorFeed<T> {
  items: T[];
  phase: FeedPhase;
  /** Why the first page failed. */
  error: unknown;
  hasMore: boolean;
  loadingMore: boolean;
  /** Set when Load more failed; the list stays and the button tries again. */
  moreError: unknown;
  loadMore: () => void;
  /** Reload from the top (after a failed first page). */
  retry: () => void;
  /** Put an item at the top (a post just created). Kept apart from the loaded pages. */
  prepend: (item: T) => void;
  /**
   * Put an item at the end (a comment just made: the newest of an oldest-first list). Kept apart
   * from the loaded pages; when a later page brings the same item, that copy wins its place.
   */
  append: (item: T) => void;
  /** Drop the item with this key (a comment just deleted) until the next fresh load. */
  remove: (key: string) => void;
}

interface State<T> {
  generation: number;
  phase: FeedPhase;
  error: unknown;
  pages: T[];
  /** Items added at the top; kept apart so one made while page 1 loads survives its arrival. */
  prepended: T[];
  /** Items added at the end; kept apart for the same reason. */
  appended: T[];
  /** Keys dropped by `remove`; cleared by every fresh load, whose answer already leaves them out. */
  removed: string[];
  nextCursor: string | null;
  loadingMore: boolean;
  moreError: unknown;
}

type Action<T> =
  | { type: "start"; generation: number; clearPrepended: boolean }
  | { type: "loaded"; generation: number; page: CursorPage<T> }
  | { type: "failed"; generation: number; error: unknown }
  | { type: "more-start"; generation: number }
  | { type: "more-loaded"; generation: number; page: CursorPage<T> }
  | { type: "more-failed"; generation: number; error: unknown }
  | { type: "prepend"; item: T }
  | { type: "append"; item: T }
  | { type: "remove"; key: string };

function initialState<T>(): State<T> {
  return {
    generation: 0,
    phase: "idle",
    error: null,
    pages: [],
    prepended: [],
    appended: [],
    removed: [],
    nextCursor: null,
    loadingMore: false,
    moreError: null,
  };
}

function reducer<T>(state: State<T>, action: Action<T>): State<T> {
  switch (action.type) {
    case "start":
      return {
        ...initialState<T>(),
        generation: action.generation,
        phase: "loading",
        prepended: action.clearPrepended ? [] : state.prepended,
        appended: action.clearPrepended ? [] : state.appended,
      };
    case "prepend":
      return { ...state, prepended: [action.item, ...state.prepended] };
    case "append":
      return { ...state, appended: [...state.appended, action.item] };
    case "remove":
      return { ...state, removed: [...state.removed, action.key] };
    default:
  }
  // Everything else answers a request: ignore it if a newer load has started since.
  if (action.generation !== state.generation) return state;
  switch (action.type) {
    case "loaded":
      return {
        ...state,
        phase: "ready",
        pages: action.page.items,
        nextCursor: action.page.nextCursor,
      };
    case "failed":
      return { ...state, phase: "error", error: action.error };
    case "more-start":
      return { ...state, loadingMore: true, moreError: null };
    case "more-loaded":
      return {
        ...state,
        loadingMore: false,
        pages: [...state.pages, ...action.page.items],
        nextCursor: action.page.nextCursor,
      };
    case "more-failed":
      return { ...state, loadingMore: false, moreError: action.error };
  }
}

/**
 * A cursor-paginated list with Load more (ARCHITECTURE §9): the first page loads when the session
 * is known, later pages append, and an item added at the top (a post just created) is never
 * repeated or lost, whatever order things arrive in; the same goes for one added at the end or
 * removed. Never loads two pages at once.
 */
export function useCursorFeed<T>(options: UseCursorFeedOptions<T>): CursorFeed<T> {
  const { enabled, resetKey } = options;
  const [state, dispatch] = useReducer(reducer<T>, undefined, initialState<T>);
  const [attempt, setAttempt] = useState(0);
  const { keyOf } = options;
  const latest = useRef(options);
  // The effects below read the newest options without re-running when they change.
  useEffect(() => {
    latest.current = options;
  });
  const generation = useRef(0);
  const loadedFor = useRef<string | null | undefined>(undefined);
  const inFlight = useRef(false);
  const moreController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const mine = ++generation.current;
    const userChanged = loadedFor.current !== undefined && loadedFor.current !== resetKey;
    loadedFor.current = resetKey;
    inFlight.current = false;
    dispatch({ type: "start", generation: mine, clearPrepended: userChanged });
    latest.current.fetchPage(null, controller.signal).then(
      (page) => dispatch({ type: "loaded", generation: mine, page }),
      (error: unknown) => {
        if (!controller.signal.aborted) dispatch({ type: "failed", generation: mine, error });
      },
    );
    return () => {
      controller.abort();
      moreController.current?.abort();
    };
  }, [enabled, resetKey, attempt]);

  const loadMore = useCallback(() => {
    if (inFlight.current || state.phase !== "ready" || !state.nextCursor) return;
    inFlight.current = true;
    const mine = state.generation;
    const controller = new AbortController();
    moreController.current = controller;
    dispatch({ type: "more-start", generation: mine });
    latest.current.fetchPage(state.nextCursor, controller.signal).then(
      (page) => {
        inFlight.current = false;
        dispatch({ type: "more-loaded", generation: mine, page });
      },
      (error: unknown) => {
        inFlight.current = false;
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 404) {
          // The cursor is gone or crafted: start again from the top.
          setAttempt((n) => n + 1);
          return;
        }
        dispatch({ type: "more-failed", generation: mine, error });
      },
    );
  }, [state.phase, state.nextCursor, state.generation]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const prepend = useCallback((item: T) => dispatch({ type: "prepend", item }), []);
  const append = useCallback((item: T) => dispatch({ type: "append", item }), []);
  const remove = useCallback((key: string) => dispatch({ type: "remove", key }), []);

  const items = useMemo(() => {
    const seen = new Set<string>(state.removed);
    const out: T[] = [];
    for (const item of [...state.prepended, ...state.pages, ...state.appended]) {
      const key = keyOf(item);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(item);
    }
    return out;
  }, [state.prepended, state.pages, state.appended, state.removed, keyOf]);

  return {
    items,
    phase: state.phase,
    error: state.error,
    hasMore: state.nextCursor !== null,
    loadingMore: state.loadingMore,
    moreError: state.moreError,
    loadMore,
    retry,
    prepend,
    append,
    remove,
  };
}
