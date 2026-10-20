/** Shared test helpers for the notifications feature (not shipped: only *.test.* files import it). */
import type { NotificationActor, NotificationData } from "@/lib/api/types";

export const BO_ACTOR: NotificationActor = {
  id: "u-2",
  username: "bo",
  display_name: "Bo Bell",
  avatar_url: null,
};

let counter = 0;

/** A like by Bo of the viewer's opinion, an hour old; override what a test is about. */
export function makeNotification(overrides: Partial<NotificationData> = {}): NotificationData {
  counter += 1;
  return {
    id: `n-${counter}`,
    type: "like",
    outcome: "",
    is_read: false,
    created_at: "2026-10-20T11:00:00Z",
    actor: BO_ACTOR,
    post: {
      id: "11111111-1111-4111-8111-111111111111",
      excerpt: "Rain is nice",
      post_type: "opinion",
      status: "published",
    },
    comment: null,
    ...overrides,
  };
}

/** The clock the items are rendered against: an hour after `makeNotification`'s default time. */
export const NOW = new Date("2026-10-20T12:00:00Z");

/** The nine kinds, each as the API sends it. */
export function oneOfEach(): NotificationData[] {
  const post = makeNotification().post;
  return [
    makeNotification({ type: "follow", post: null, actor: { ...BO_ACTOR, following: false } }),
    makeNotification({ type: "like" }),
    makeNotification({ type: "comment", comment: { id: "c-1", excerpt: "Agreed, mostly" } }),
    makeNotification({ type: "repost" }),
    makeNotification({
      type: "verdict",
      outcome: "true",
      actor: null,
      post: post && { ...post, post_type: "fact", status: "verified_true" },
    }),
    makeNotification({ type: "under_review", actor: null }),
    makeNotification({ type: "removed", actor: null }),
    makeNotification({ type: "emergency_demoted", actor: null }),
    makeNotification({ type: "appeal_resolved", outcome: "upheld", actor: null }),
  ];
}
