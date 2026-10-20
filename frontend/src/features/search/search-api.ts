/**
 * `GET /api/v1/search/` (ARCHITECTURE §9, Part 12). An ordinary app call: the token is sent when
 * there is one (so `liked_by_me` and `is_following` are right) with the client's single
 * refresh-and-retry. The cursor is the next page number, an opaque string to us.
 */
import { api } from "@/lib/api/client";
import type { FeedResponse, UserListResponse } from "@/lib/api/types";
import type { FeedPage } from "@/features/posts/posts-api";
import { type UserPage, withCursor } from "@/features/social/social-api";
import { FILTER_PARAMS, type SearchFilter } from "./search-params";

export const SEARCH_PATH = "/v1/search/";

/** One page of post results, best match first. */
export async function searchPosts(
  q: string,
  filter: SearchFilter,
  cursor: string | null,
  signal?: AbortSignal,
): Promise<FeedPage> {
  const path = withCursor(SEARCH_PATH, cursor, { q, type: "posts", ...FILTER_PARAMS[filter] });
  const body = await api.get<FeedResponse>(path, { signal });
  return { items: body.results, nextCursor: body.next_cursor };
}

/** One page of people. */
export async function searchPeople(
  q: string,
  cursor: string | null,
  signal?: AbortSignal,
): Promise<UserPage> {
  const path = withCursor(SEARCH_PATH, cursor, { q, type: "users" });
  const body = await api.get<UserListResponse>(path, { signal });
  return { items: body.results, nextCursor: body.next_cursor };
}
