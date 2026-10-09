/**
 * The social-graph endpoints (ARCHITECTURE §9, Part 6). Ordinary app calls: they send the in-memory
 * access token and get the client's single refresh-and-retry on a 401, so `token: false` is never
 * used here (a profile is public, but `is_following` and `is_me` need to know who is asking).
 */
import { api } from "@/lib/api/client";
import type { FeedResponse, UserListResponse, UserProfile, UserRowData } from "@/lib/api/types";
import type { FeedPage } from "@/features/posts/posts-api";

export const SOCIAL_PATHS = {
  feed: "/v1/feed/",
  user: (username: string) => `/v1/users/${encodeURIComponent(username)}/`,
} as const;

export type PostFilter = "all" | "fact" | "opinion";

export interface UserPage {
  items: UserRowData[];
  nextCursor: string | null;
}

function withCursor(path: string, cursor: string | null, extra: Record<string, string> = {}) {
  const params = new URLSearchParams(extra);
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

/** One page of the Following feed: the people you follow and you, newest first. */
export async function fetchFollowingFeed(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<FeedPage> {
  const body = await api.get<FeedResponse>(withCursor(SOCIAL_PATHS.feed, cursor), { signal });
  return { items: body.results, nextCursor: body.next_cursor };
}

export function fetchProfile(username: string, signal?: AbortSignal): Promise<UserProfile> {
  return api.get<UserProfile>(SOCIAL_PATHS.user(username), { signal });
}

/** One page of a user's posts the public can see. `all` sends no filter. */
export async function fetchUserPosts(
  username: string,
  filter: PostFilter,
  cursor: string | null,
  signal?: AbortSignal,
): Promise<FeedPage> {
  const extra: Record<string, string> = filter === "all" ? {} : { post_type: filter };
  const path = withCursor(`${SOCIAL_PATHS.user(username)}posts/`, cursor, extra);
  const body = await api.get<FeedResponse>(path, { signal });
  return { items: body.results, nextCursor: body.next_cursor };
}

export type ConnectionKind = "followers" | "following";

/** One page of a user's followers or of the people they follow, newest follow first. */
export async function fetchConnections(
  username: string,
  kind: ConnectionKind,
  cursor: string | null,
  signal?: AbortSignal,
): Promise<UserPage> {
  const path = withCursor(`${SOCIAL_PATHS.user(username)}${kind}/`, cursor);
  const body = await api.get<UserListResponse>(path, { signal });
  return { items: body.results, nextCursor: body.next_cursor };
}

/** Follow: 201 the first time, 200 after. Needs a verified email (403 `email_unverified`). */
export function followUser(username: string): Promise<{ is_following: true }> {
  return api.post<{ is_following: true }>(`${SOCIAL_PATHS.user(username)}follow/`);
}

/** Unfollow: 204 whether or not you were following. */
export function unfollowUser(username: string): Promise<void> {
  return api.del(`${SOCIAL_PATHS.user(username)}follow/`);
}
