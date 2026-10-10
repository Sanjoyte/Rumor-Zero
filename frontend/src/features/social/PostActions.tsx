import type { Post } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { BookmarkButton } from "./BookmarkButton";
import { CommentCountLink } from "./CommentCountLink";
import { LikeButton } from "./LikeButton";
import { RepostButton } from "./RepostButton";
import { repostBlockedReason } from "./repost-rules";

export interface PostActionsProps {
  post: Pick<
    Post,
    | "id"
    | "status"
    | "is_mine"
    | "liked_by_me"
    | "like_count"
    | "comment_count"
    | "reposted_by_me"
    | "repost_count"
    | "bookmarked_by_me"
  >;
  /** "card" is the feed card's footer (Stitch b1); "detail" sits in the post page's action row. */
  variant?: "card" | "detail";
}

/**
 * The action bar: like, comment, repost, and the private bookmark (Stitch b1/b3). On a card the
 * bookmark sits at the right (b1's `justify-between`) and the comment link goes to the post's
 * discussion; on the post page everything is one row and the link jumps to the section below. A
 * repost item's buttons act on the original post (`post.id`): there is no id for the repost itself.
 */
export function PostActions({ post, variant = "card" }: PostActionsProps) {
  const detail = variant === "detail";
  const group = "flex items-center gap-space-lg";
  const buttons = (
    <div className={group}>
      <LikeButton
        postId={post.id}
        initialLiked={post.liked_by_me}
        initialCount={post.like_count}
        showLabel={detail}
      />
      <CommentCountLink
        href={detail ? "#comments" : `/p/${post.id}#comments`}
        count={post.comment_count}
        showLabel={detail}
      />
      <RepostButton
        postId={post.id}
        initialReposted={post.reposted_by_me}
        initialCount={post.repost_count}
        blockedReason={repostBlockedReason(post)}
        showLabel={detail}
      />
      {detail && <BookmarkButton postId={post.id} initialBookmarked={post.bookmarked_by_me} />}
    </div>
  );
  if (detail) {
    return (
      <div className="flex items-center font-label-code text-label-code text-outline">
        {buttons}
      </div>
    );
  }
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-space-md border-t border-outline-variant/20 pt-space-sm",
        "font-label-code text-label-code text-outline",
      )}
    >
      {buttons}
      <BookmarkButton postId={post.id} initialBookmarked={post.bookmarked_by_me} />
    </div>
  );
}
