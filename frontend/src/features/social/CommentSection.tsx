"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import type { Comment } from "@/lib/api/types";
import { CommentComposer } from "./CommentComposer";
import { CommentList } from "./CommentList";
import { DeleteCommentModal } from "./DeleteCommentModal";
import { SOCIAL_MESSAGES } from "./messages";
import { useComments } from "./useComments";

/**
 * The discussion under a post (Stitch b3, flat): the heading with the count, the composer and the
 * list. The page owns the post, so it hears about each change in the number of comments
 * (`onCountChange`) and the heading follows its `count`.
 */
export function CommentSection({
  postId,
  count,
  onCountChange,
  now,
}: {
  postId: string;
  count: number;
  /** The new total after a comment is added or deleted. */
  onCountChange: (count: number) => void;
  now?: Date;
}) {
  const toast = useToast();
  const feed = useComments(postId);
  const { append, remove } = feed;
  const [deleting, setDeleting] = useState<string | null>(null);

  function posted(comment: Comment) {
    append(comment);
    onCountChange(count + 1);
    toast.show("Comment posted.", { tone: "success" });
  }

  function deleted(commentId: string) {
    remove(commentId);
    onCountChange(Math.max(0, count - 1));
    setDeleting(null);
    toast.show(SOCIAL_MESSAGES.commentDeleted, { tone: "success" });
  }

  return (
    <section
      id="comments"
      aria-labelledby="comments-heading"
      className="flex scroll-mt-24 flex-col gap-space-md pb-space-xl"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-space-sm">
        <h2 id="comments-heading" className="font-headline-sm text-headline-sm text-on-surface">
          Comments ({count})
        </h2>
        <span className="font-label-code text-label-code text-on-surface-variant uppercase">
          Oldest first
        </span>
      </div>
      <CommentComposer postId={postId} onPosted={posted} />
      <CommentList feed={feed} onDelete={(comment) => setDeleting(comment.id)} now={now} />
      <DeleteCommentModal
        commentId={deleting}
        onClose={() => setDeleting(null)}
        onDeleted={deleted}
      />
    </section>
  );
}
