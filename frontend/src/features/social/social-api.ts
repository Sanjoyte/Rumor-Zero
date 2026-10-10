/**
 * The social-graph endpoints (ARCHITECTURE §9, Part 6). Ordinary app calls: they send the in-memory
 * access token and get the client's single refresh-and-retry on a 401, so `token: false` is never
 * used here (a profile is public, but `is_following` and `is_me` need to know who is asking).
 */
import { api } from "@/lib/api/client";
import type {
  Comment,
  CursorPage,
  FeedResponse,
  UserListResponse,
  UserProfile,
  UserRowData,
} from "@/lib/api/types";
import type { FeedPage } from "@/features/posts/posts-api";

export const SOCIAL_PATHS = {
  feed: "/v1/feed/",
  user: (username: string) => `/v1/users/${encodeURIComponent(username)}/`,
  like: (postId: string) => `/v1/posts/${encodeURIComponent(postId)}/like/`,
  repost: (postId: string) => `/v1/posts/${encodeURIComponent(postId)}/repost/`,
  bookmark: (postId: string) => `/v1/posts/${encodeURIComponent(postId)}/bookmark/`,
  bookmarks: "/v1/me/bookmarks/",
  comments: (postId: string) => `/v1/posts/${encodeURIComponent(postId)}/comments/`,
  comment: (commentId: string) => `/v1/comments/${encodeURIComponent(commentId)}/`,
} as const;

export type PostFilter = "all" | "fact" | "opinion";

export interface UserPage {
  items: UserRowData[];
  nextCursor: string | null;
}

export function withCursor(
  path: string,
  cursor: string | null,
  extra: Record<string, string> = {},
) {
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

/** Like a post: 201 the first time, 200 after. Needs a verified email (403 `email_unverified`). */
export function likePost(postId: string): Promise<{ liked: true }> {
  return api.post<{ liked: true }>(SOCIAL_PATHS.like(postId));
}

/** Take a like back: 204 whether or not you had liked it. */
export function unlikePost(postId: string): Promise<void> {
  return api.del(SOCIAL_PATHS.like(postId));
}

/** Repost: 201 the first time, 200 after. A verified email; 409 for your own or a FALSE post. */
export function repostPost(postId: string): Promise<{ reposted: true }> {
  return api.post<{ reposted: true }>(SOCIAL_PATHS.repost(postId));
}

/** Take a repost back: 204 whether or not you had reposted it, and also when the original is gone. */
export function unrepostPost(postId: string): Promise<void> {
  return api.del(SOCIAL_PATHS.repost(postId));
}

/** Save a post privately: 201 the first time, 200 after. Any signed-in user. */
export function bookmarkPost(postId: string): Promise<{ bookmarked: true }> {
  return api.post<{ bookmarked: true }>(SOCIAL_PATHS.bookmark(postId));
}

/** Take a bookmark back: 204 whether or not you had saved it. */
export function unbookmarkPost(postId: string): Promise<void> {
  return api.del(SOCIAL_PATHS.bookmark(postId));
}

/** One page of your own bookmarks, the newest bookmark first (private: never anyone else's). */
export async function fetchBookmarks(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<FeedPage> {
  const body = await api.get<FeedResponse>(withCursor(SOCIAL_PATHS.bookmarks, cursor), { signal });
  return { items: body.results, nextCursor: body.next_cursor };
}

export interface CommentPage {
  items: Comment[];
  nextCursor: string | null;
}

/**
 * One page of a post's comments, oldest first. Public, but sent with the token when there is one
 * so each comment knows whether it is yours (`is_mine`).
 */
export async function fetchComments(
  postId: string,
  cursor: string | null,
  signal?: AbortSignal,
): Promise<CommentPage> {
  const body = await api.get<CursorPage<Comment>>(
    withCursor(SOCIAL_PATHS.comments(postId), cursor),
    {
      signal,
    },
  );
  return { items: body.results, nextCursor: body.next_cursor };
}

/** Add a comment (a verified email; 400 on `content`, 404 for a post that is gone). */
export function createComment(postId: string, content: string): Promise<Comment> {
  return api.post<Comment>(SOCIAL_PATHS.comments(postId), { content });
}

/** Delete your own comment: 204; a second call or a hidden comment is 404. */
export function deleteComment(commentId: string): Promise<void> {
  return api.del(SOCIAL_PATHS.comment(commentId));
}
