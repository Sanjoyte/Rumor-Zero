import type { Post } from "@/lib/api/types";
import type { PostCardProps } from "./PostCard";

/** The API post (snake_case, ARCHITECTURE §9) as the presentational card's props. */
export function toPostCardProps(post: Post): PostCardProps {
  return {
    author: {
      displayName: post.author.display_name,
      username: post.author.username,
      avatarUrl: post.author.avatar_url,
    },
    content: post.content,
    postType: post.post_type,
    status: post.status,
    confidenceScore: post.confidence_score,
    verdictSource: post.verdict_source,
    emergencyActive: post.emergency_active,
    appealPending: post.appeal_status === "open",
    createdAt: post.created_at,
    sources: post.sources,
  };
}
