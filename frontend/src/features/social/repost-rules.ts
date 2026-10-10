import type { Post } from "@/lib/api/types";
import { SOCIAL_MESSAGES } from "./messages";

/**
 * Why a post can't be reposted, or null when it can (ARCHITECTURE §4d): your own post, a post
 * labelled FALSE, or a removed one. The server decides and answers 409/404; this lets the button
 * say so before the click. A repost you already made is never blocked (you can take it back).
 */
export function repostBlockedReason(post: Pick<Post, "is_mine" | "status">): string | null {
  if (post.is_mine) return SOCIAL_MESSAGES.cannotRepostOwn;
  if (post.status === "verified_false") return SOCIAL_MESSAGES.cannotRepostFalse;
  if (post.status === "removed") return SOCIAL_MESSAGES.cannotRepostRemoved;
  return null;
}
