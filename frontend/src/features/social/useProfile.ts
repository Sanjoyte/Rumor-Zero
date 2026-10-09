"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import type { UserProfile } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fetchProfile } from "./social-api";

export type ProfilePhase = "ready" | "loading" | "not-found" | "error";

export interface ProfileState {
  profile: UserProfile | null;
  phase: ProfilePhase;
  /** True once `is_following` and `is_me` are the current viewer's (the server render is not). */
  viewerReady: boolean;
  retry: () => void;
  /** Move the follower count by one after a follow or unfollow, and remember the new state. */
  followed: (following: boolean) => void;
}

/**
 * The profile on `/u/[username]` and the people lists. It starts from what the server rendered
 * (`initial`, the anonymous view), so the page is complete without a request. An anonymous visitor
 * keeps that view; a signed-in visitor fetches once to learn `is_following` and `is_me`, and again
 * if the user changes. Without `initial` it fetches as soon as the session is known. 404 means no
 * such account. (A viewer is marked as fetched only on success: StrictMode aborts the first request.)
 */
export function useProfile(username: string, initial: UserProfile | null): ProfileState {
  const { status, user } = useAuth();
  const [state, setState] = useState<{
    profile: UserProfile | null;
    phase: ProfilePhase;
    viewFor: string | null;
  }>({
    profile: initial,
    phase: initial ? "ready" : "loading",
    viewFor: initial ? "anonymous" : null,
  });
  const controller = useRef<AbortController | null>(null);
  const viewer = status === "authenticated" && user ? user.id : "anonymous";

  const load = useCallback(
    (silent: boolean, forViewer: string) => {
      controller.current?.abort();
      const mine = new AbortController();
      controller.current = mine;
      fetchProfile(username, mine.signal).then(
        (profile) => {
          if (!mine.signal.aborted) setState({ profile, phase: "ready", viewFor: forViewer });
        },
        (error: unknown) => {
          if (mine.signal.aborted) return;
          if (error instanceof ApiError && error.status === 404) {
            setState({ profile: null, phase: "not-found", viewFor: forViewer });
          } else if (!silent) {
            setState((prev) => (prev.profile ? prev : { ...prev, phase: "error" }));
          }
        },
      );
    },
    [username],
  );

  useEffect(() => {
    if (status === "loading" || state.viewFor === viewer) return;
    load(state.profile !== null, viewer);
    // `state` only decides whether the fetch is needed and how loud a failure is.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, viewer, load]);

  useEffect(() => () => controller.current?.abort(), []);

  const retry = useCallback(() => {
    setState((prev) => (prev.profile ? prev : { ...prev, phase: "loading" }));
    load(false, viewer);
  }, [load, viewer]);

  const followed = useCallback((following: boolean) => {
    setState((prev) =>
      prev.profile
        ? {
            ...prev,
            profile: {
              ...prev.profile,
              is_following: following,
              counts: {
                ...prev.profile.counts,
                followers: Math.max(0, prev.profile.counts.followers + (following ? 1 : -1)),
              },
            },
          }
        : prev,
    );
  }, []);

  return {
    profile: state.profile,
    phase: state.phase,
    viewerReady: status !== "loading" && state.viewFor === viewer,
    retry,
    followed,
  };
}
