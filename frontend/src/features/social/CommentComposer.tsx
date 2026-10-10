"use client";

import Link from "next/link";
import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Textarea } from "@/components/ui/Textarea";
import type { Comment } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { loginRedirectFor } from "@/lib/auth/route-guard";
import { countCharacters } from "@/lib/format";
import { commentFailureMessage, SOCIAL_MESSAGES } from "./messages";
import { createComment } from "./social-api";

export const MAX_COMMENT_LENGTH = 500;

/** The client-side twin of the server's rule: trimmed, 1 to 500 code points. */
export function commentProblem(text: string): string | null {
  const trimmed = text.trim();
  if (trimmed === "") return SOCIAL_MESSAGES.commentBlank;
  if (countCharacters(trimmed) > MAX_COMMENT_LENGTH) return SOCIAL_MESSAGES.commentTooLong;
  return null;
}

/**
 * The comment box on the post page (Stitch b3's composer, with a character counter and Ctrl+Enter
 * instead of its attach buttons). Visitors get a link to log in; an unverified email gets the box
 * locked with the reason. The draft is kept when sending fails and cleared when it works. One
 * request at a time.
 */
export function CommentComposer({
  postId,
  onPosted,
}: {
  postId: string;
  /** Called with the server's comment once it is saved. */
  onPosted: (comment: Comment) => void;
}) {
  const { status, user } = useAuth();
  const fieldId = useId();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const inFlight = useRef(false);
  const refocus = useRef(false);

  // A disabled field drops focus. Once sending ends and the box is enabled again, give it back so
  // the next comment can be typed at once.
  useEffect(() => {
    if (!sending && refocus.current) {
      refocus.current = false;
      document.getElementById(fieldId)?.focus();
    }
  }, [sending, fieldId]);

  if (status === "loading") return <Skeleton className="h-32 w-full" />;

  if (status === "anonymous" || !user) {
    return (
      <Alert tone="info">
        <Link
          href={loginRedirectFor(`/p/${postId}`)}
          prefetch={false}
          className="font-semibold text-secondary hover:underline"
        >
          {SOCIAL_MESSAGES.logInToComment}
        </Link>{" "}
        to join the discussion.
      </Alert>
    );
  }

  const locked = !user.is_email_verified;

  async function submit() {
    if (inFlight.current || locked) return;
    const problem = commentProblem(text);
    if (problem) {
      setError(problem);
      document.getElementById(fieldId)?.focus();
      return;
    }
    inFlight.current = true;
    setSending(true);
    setError(null);
    try {
      const comment = await createComment(postId, text.trim());
      setText("");
      onPosted(comment);
    } catch (caught) {
      setError(commentFailureMessage(caught));
    } finally {
      inFlight.current = false;
      refocus.current = true;
      setSending(false);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      void submit();
    }
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
      noValidate
      className="flex flex-col gap-space-sm"
    >
      <fieldset disabled={locked || sending} className="flex min-w-0 flex-col gap-space-sm">
        <Textarea
          id={fieldId}
          label="Add a comment"
          hideLabel
          placeholder="Add a comment…"
          rows={3}
          maxCount={MAX_COMMENT_LENGTH}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            if (error) setError(null);
          }}
          onKeyDown={onKeyDown}
          error={error}
        />
        <div className="flex items-center justify-end gap-space-md">
          <span className="hidden font-label-code text-label-code text-outline sm:inline">
            Ctrl + Enter to post
          </span>
          <Button type="submit" loading={sending}>
            Comment
          </Button>
        </div>
      </fieldset>
      {locked && <Alert tone="info">{SOCIAL_MESSAGES.verifyToComment}</Alert>}
    </form>
  );
}
