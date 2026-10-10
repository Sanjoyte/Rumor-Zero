"use client";

import { useCallback } from "react";
import { useCursorFeed, type CursorFeed } from "@/features/posts/useCursorFeed";
import type { Comment } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fetchComments } from "./social-api";

const commentKey = (comment: Comment) => comment.id;

/**
 * One post's comments, oldest first, as a cursor feed: the first page loads when the session is
 * known (so each comment knows whether it is yours), Load more appends, a comment you just made
 * is `append`ed at the end and one you deleted is `remove`d. Mount it under a `key` with the post
 * id: `useCursorFeed` doesn't refetch when `fetchPage` changes.
 */
export function useComments(postId: string): CursorFeed<Comment> {
  const { status, user } = useAuth();
  const fetchPage = useCallback(
    (cursor: string | null, signal: AbortSignal) => fetchComments(postId, cursor, signal),
    [postId],
  );
  return useCursorFeed<Comment>({
    fetchPage,
    keyOf: commentKey,
    enabled: status !== "loading",
    resetKey: user?.id ?? null,
  });
}
