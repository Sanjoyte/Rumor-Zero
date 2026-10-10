"use client";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadMore } from "@/components/ui/LoadMore";
import { Skeleton } from "@/components/ui/Skeleton";
import type { CursorFeed } from "@/features/posts/useCursorFeed";
import type { Comment } from "@/lib/api/types";
import { CommentItem } from "./CommentItem";
import { commentsErrorMessage, SOCIAL_MESSAGES } from "./messages";

/**
 * The comments, oldest first: skeletons while the first page loads, an error with "Try again", an
 * empty state, the rows, and "Load more comments" at the end (a failed one keeps the list and says
 * so beside the button).
 */
export function CommentList({
  feed,
  onDelete,
  now,
}: {
  feed: CursorFeed<Comment>;
  onDelete: (comment: Comment) => void;
  now?: Date;
}) {
  if (feed.phase === "idle" || feed.phase === "loading") {
    return (
      <div aria-busy="true" className="flex flex-col gap-space-sm">
        <span className="sr-only">Loading comments…</span>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (feed.phase === "error") {
    return (
      <Alert tone="error" title="Couldn't load the comments">
        <p>{commentsErrorMessage(feed.error)}</p>
        <Button variant="secondary" onClick={feed.retry} className="mt-space-md">
          Try again
        </Button>
      </Alert>
    );
  }
  if (feed.items.length === 0) {
    return (
      <EmptyState icon="chat_bubble" title="No comments yet">
        Start the discussion.
      </EmptyState>
    );
  }
  return (
    <div className="flex flex-col gap-space-sm">
      {feed.items.map((comment) => (
        <CommentItem key={comment.id} comment={comment} onDelete={onDelete} now={now} />
      ))}
      {feed.moreError !== null && (
        <Alert tone="error">{SOCIAL_MESSAGES.moreCommentsFailed} Try again.</Alert>
      )}
      {feed.hasMore && (
        <LoadMore hasMore loading={feed.loadingMore} onClick={feed.loadMore} className="pb-0" />
      )}
    </div>
  );
}
