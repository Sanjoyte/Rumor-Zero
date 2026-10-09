"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import type { Post } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fetchPost } from "./posts-api";

export type DetailPhase = "ready" | "loading" | "not-found" | "error";

export interface PostDetailState {
  post: Post | null;
  phase: DetailPhase;
  /** Fetch the post again without a loading state (after a polled status change). */
  reload: () => void;
  /** Try again after an error. */
  retry: () => void;
  /** Merge fields into the post we have (a polled status). */
  patch: (fields: Partial<Post>) => void;
}

/**
 * The post on `/p/[id]`. It starts from what the server rendered (`initial`, the anonymous view),
 * so the page is complete without a request. An anonymous visitor keeps that view (no request); a
 * signed-in visitor fetches once to get the personal parts (`is_mine`, the full text of their own
 * removed post), and the fetch repeats if the user changes. Without `initial` (the server couldn't
 * reach the backend) it fetches as soon as the session is known. 404 means gone.
 */
export function usePostDetail(id: string, initial: Post | null): PostDetailState {
  const { status, user } = useAuth();
  const [state, setState] = useState<{ post: Post | null; phase: DetailPhase }>({
    post: initial,
    phase: initial ? "ready" : "loading",
  });
  // Which viewer the post we hold was fetched for: the server render is the anonymous view.
  const viewOf = useRef<string | null>(initial ? "anonymous" : null);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback(
    (silent: boolean, forViewer?: string) => {
      controller.current?.abort();
      const mine = new AbortController();
      controller.current = mine;
      fetchPost(id, mine.signal).then(
        (post) => {
          if (mine.signal.aborted) return;
          // Only now is this viewer's view in hand. (Marking it earlier breaks under StrictMode:
          // the effect's cleanup aborts the request and the re-run would find it "done".)
          if (forViewer) viewOf.current = forViewer;
          setState({ post, phase: "ready" });
        },
        (error: unknown) => {
          if (mine.signal.aborted) return;
          if (error instanceof ApiError && error.status === 404) {
            setState({ post: null, phase: "not-found" });
          } else if (!silent) {
            setState((prev) => (prev.post ? prev : { post: null, phase: "error" }));
          }
        },
      );
    },
    [id],
  );

  const viewer = status === "authenticated" && user ? user.id : "anonymous";
  useEffect(() => {
    if (status === "loading" || viewOf.current === viewer) return;
    load(state.post !== null, viewer);
    // `state.post` only decides how loud a failure is, so it isn't a trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, viewer, load]);

  useEffect(() => () => controller.current?.abort(), []);

  const reload = useCallback(() => load(true), [load]);
  const retry = useCallback(() => {
    setState((prev) => (prev.post ? prev : { post: null, phase: "loading" }));
    load(false);
  }, [load]);
  const patch = useCallback(
    (fields: Partial<Post>) =>
      setState((prev) => (prev.post ? { ...prev, post: { ...prev.post, ...fields } } : prev)),
    [],
  );

  return { post: state.post, phase: state.phase, reload, retry, patch };
}
