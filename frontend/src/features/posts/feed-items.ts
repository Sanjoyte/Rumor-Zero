import type { FeedItem, Post, UnavailablePost } from "@/lib/api/types";

/** A repost whose original was deleted or removed carries `{id, unavailable: true}` (ARCHITECTURE §9). */
export function isUnavailable(post: Post | UnavailablePost): post is UnavailablePost {
  return "unavailable" in post;
}

/**
 * What a list shows, in order. A post item whose post the poll found deleted is dropped. A post
 * that already appears higher up is shown once: the API only promises "once per page", so an older
 * activity of the same post (the original after its repost, or another reposter) can come back on
 * a later page (user decision 2026-10-10). That also keeps one post's buttons from drifting apart.
 * `alreadyShown` are the posts shown above the list (the pinned emergencies, Part 11C): a later
 * repeat of one of them, or a repost of it, is hidden too.
 */
export function visibleItems(
  items: readonly FeedItem[],
  gone?: ReadonlySet<string>,
  alreadyShown?: ReadonlySet<string>,
): FeedItem[] {
  const seen = new Set<string>(alreadyShown);
  const shown: FeedItem[] = [];
  for (const item of items) {
    const id = item.post.id;
    if (item.kind === "post" && gone?.has(id)) continue;
    if (seen.has(id)) continue;
    seen.add(id);
    shown.push(item);
  }
  return shown;
}
