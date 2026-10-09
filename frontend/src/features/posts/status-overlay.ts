/**
 * Polled statuses sit in an overlay on top of the loaded feed instead of rewriting it: the feed
 * hook keeps owning its pages, a reload can't resurrect an older status, and the cards just read
 * the merged post.
 */
import type { FeedItem, Post, PostStatusUpdate } from "@/lib/api/types";

export type StatusOverlay = Readonly<Record<string, PostStatusUpdate>>;

/** The post with the freshest status, confidence and verdict source we know of. */
export function applyStatus(post: Post, overlay: StatusOverlay): Post {
  const update = overlay[post.id];
  if (!update) return post;
  if (
    update.status === post.status &&
    update.confidence_score === post.confidence_score &&
    update.verdict_source === post.verdict_source
  ) {
    return post;
  }
  return {
    ...post,
    status: update.status,
    confidence_score: update.confidence_score,
    verdict_source: update.verdict_source,
  };
}

/** The ids of the posts that were loaded as `pending`: the ones worth polling. */
export function pendingPostIds(items: readonly FeedItem[]): string[] {
  const ids: string[] = [];
  for (const item of items) {
    if (item.kind === "post" && item.post.status === "pending") ids.push(item.post.id);
  }
  return ids;
}
