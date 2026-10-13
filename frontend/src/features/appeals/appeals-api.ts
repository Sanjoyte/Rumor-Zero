/**
 * The appeal endpoint (ARCHITECTURE §4, §9, Part 11). An ordinary app call: it sends the in-memory
 * access token and gets the client's single refresh-and-retry on a 401. The answer is the post as
 * its author now sees it (a FALSE post comes back under review, with `appeal_status: "open"`).
 */
import { api } from "@/lib/api/client";
import type { Post } from "@/lib/api/types";

export const APPEAL_PATHS = {
  appeal: (postId: string) => `/v1/posts/${encodeURIComponent(postId)}/appeal/`,
} as const;

/** The most the server accepts for the author's words, counted in code points. */
export const MAX_APPEAL_REASON = 500;

export interface AppealBody {
  /** Trimmed. Optional: an empty string says nothing. */
  reason: string;
}

export function appealPost(postId: string, body: AppealBody): Promise<Post> {
  return api.post<Post>(APPEAL_PATHS.appeal(postId), body);
}
