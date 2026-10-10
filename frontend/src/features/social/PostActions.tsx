import { cn } from "@/lib/cn";
import { CommentCountLink } from "./CommentCountLink";
import { LikeButton } from "./LikeButton";

export interface PostActionsProps {
  postId: string;
  liked: boolean;
  likeCount: number;
  commentCount: number;
  /** "card" is the feed card's footer (Stitch b1); "detail" sits in the post page's action row. */
  variant?: "card" | "detail";
}

/**
 * The like and comment buttons (Part 7; repost and bookmark join in 7B). On a card the comment
 * link goes to the post's discussion; on the post page it jumps to the section below.
 */
export function PostActions({
  postId,
  liked,
  likeCount,
  commentCount,
  variant = "card",
}: PostActionsProps) {
  const detail = variant === "detail";
  return (
    <div
      className={cn(
        "flex items-center gap-space-lg font-label-code text-label-code text-outline",
        !detail && "border-t border-outline-variant/20 pt-space-sm",
      )}
    >
      <LikeButton
        postId={postId}
        initialLiked={liked}
        initialCount={likeCount}
        showLabel={detail}
      />
      <CommentCountLink
        href={detail ? "#comments" : `/p/${postId}#comments`}
        count={commentCount}
        showLabel={detail}
      />
    </div>
  );
}
