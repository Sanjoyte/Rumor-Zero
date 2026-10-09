/**
 * The post endpoints (ARCHITECTURE §9). Ordinary app calls: they send the in-memory access token
 * and get the client's single refresh-and-retry on a 401, so `token: false` is never used here.
 */
import { api } from "@/lib/api/client";
import type { CreatePostBody, FactQuota, FeedItem, FeedResponse, Post } from "@/lib/api/types";

export const POSTS_PATHS = {
  posts: "/v1/posts/",
  factQuota: "/v1/me/fact-quota/",
} as const;

export interface FeedPage {
  items: FeedItem[];
  nextCursor: string | null;
}

export function createPost(body: CreatePostBody): Promise<Post> {
  return api.post<Post>(POSTS_PATHS.posts, body);
}

/** One page of the public Recent feed, newest first. `cursor` is the opaque `next_cursor`. */
export async function fetchRecentFeed(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<FeedPage> {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  const body = await api.get<FeedResponse>(`${POSTS_PATHS.posts}${query}`, { signal });
  return { items: body.results, nextCursor: body.next_cursor };
}

export function fetchFactQuota(signal?: AbortSignal): Promise<FactQuota> {
  return api.get<FactQuota>(POSTS_PATHS.factQuota, { signal });
}

/** A stable key for a feed entry: a post by its id, a repost by who reposted what (Part 7B). */
export function feedItemKey(item: FeedItem): string {
  return item.kind === "post" ? item.post.id : `repost:${item.reposted_by.id}:${item.post.id}`;
}
