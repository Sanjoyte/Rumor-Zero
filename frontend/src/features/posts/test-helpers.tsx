/** Shared test helpers for the posts feature (not shipped: only *.test.* files import it). */
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { ME, testSession } from "@/features/auth/test-helpers";
import type { FactQuota, FeedItem, Me, Post, UserSummary } from "@/lib/api/types";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { ComposerProvider } from "./ComposerProvider";

export const VERIFIED_ME: Me = { ...ME, is_email_verified: true };

export function makePost(overrides: Partial<Post> = {}): Post {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    author: { id: "u-1", username: "ada", display_name: "Ada", avatar_url: null },
    content: "Rain is nice",
    post_type: "opinion",
    status: "published",
    sources: [],
    is_emergency: false,
    emergency_active: false,
    emergency_expires_at: null,
    emergency_demoted: false,
    confidence_score: null,
    verdict_source: null,
    verdict_note: "",
    like_count: 0,
    comment_count: 0,
    repost_count: 0,
    liked_by_me: false,
    reposted_by_me: false,
    bookmarked_by_me: false,
    reported_by_me: false,
    is_mine: true,
    can_appeal: false,
    appeal_status: null,
    removal_reason: "",
    created_at: "2026-10-08T12:00:00Z",
    ...overrides,
  };
}

export function feedEntry(post: Post): FeedItem {
  return { kind: "post", post, reposted_by: null, activity_at: post.created_at };
}

/** Someone who reposts (the author of `makePost` is `ada`). */
export const BO: UserSummary = { id: "u-2", username: "bo", display_name: "Bo", avatar_url: null };

/** A repost of `post` by `by`, at its own time. */
export function repostEntry(
  post: Post,
  by: UserSummary = BO,
  activityAt = "2026-10-08T13:00:00Z",
): FeedItem {
  return { kind: "repost", post, reposted_by: by, activity_at: activityAt };
}

/** A repost whose original is deleted or removed. */
export function unavailableEntry(postId: string, by: UserSummary = BO): FeedItem {
  return {
    kind: "repost",
    post: { id: postId, unavailable: true },
    reposted_by: by,
    activity_at: "2026-10-08T13:00:00Z",
  };
}

export function makeQuota(overrides: Partial<FactQuota> = {}): FactQuota {
  return {
    limit: 10,
    used: 3,
    remaining: 7,
    window_hours: 24,
    next_slot_at: null,
    emergency: { allowed: true, reason: null, next_allowed_at: null, block_days: 30 },
    ...overrides,
  };
}

export type SessionKind = "verified" | "unverified" | "anonymous" | "loading";

/** A session of the given kind; `loading` never finishes restoring. */
export function sessionOf(kind: SessionKind) {
  const refresh =
    kind === "loading"
      ? vi.fn(() => new Promise<string>(() => {}))
      : vi.fn(async () => "access-token");
  return testSession(
    {
      refresh,
      fetchMe: vi.fn(async () => (kind === "verified" ? VERIFIED_ME : ME)),
    },
    { loggedIn: kind !== "anonymous" },
  );
}

/** The auth session, the toast region and the composer around `ui`. */
export function renderWithComposer(
  ui: ReactNode,
  kind: SessionKind = "verified",
  { session = sessionOf(kind) } = {},
) {
  const view = render(
    <AuthProvider session={session.session}>
      <ToastProvider>
        <ComposerProvider now={new Date("2026-10-08T12:00:00Z")} timeZone="UTC">
          {ui}
        </ComposerProvider>
      </ToastProvider>
    </AuthProvider>,
  );
  return { ...view, ...session };
}

/**
 * The auth session and the toast region around `ui`, without the composer (no router needed).
 * `rerender` keeps the providers, so a test can change props without losing the session.
 */
export function renderWithSessionAndToast(
  ui: ReactNode,
  kind: SessionKind = "verified",
  { session = sessionOf(kind) } = {},
) {
  const wrap = (node: ReactNode) => (
    <AuthProvider session={session.session}>
      <ToastProvider>{node}</ToastProvider>
    </AuthProvider>
  );
  const view = render(wrap(ui));
  return { ...view, ...session, rerender: (next: ReactNode) => view.rerender(wrap(next)) };
}
