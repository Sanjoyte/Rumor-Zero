"use client";

import Link from "next/link";
import { type ReactNode, useId, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth/AuthProvider";
import { loginRedirectFor } from "@/lib/auth/route-guard";
import { cn } from "@/lib/cn";
import { formatCompactNumber } from "@/lib/format";
import { likeFailureMessage, SOCIAL_MESSAGES } from "./messages";
import { likePost, unlikePost } from "./social-api";

/** The b1/a1 action-bar button: glyph and count, above the card's stretched claim link. */
export const ACTION_CLASSES =
  "relative z-10 flex items-center gap-space-xs rounded-lg transition-colors hover:text-on-surface focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none";

export interface LikeButtonProps {
  postId: string;
  /** What the server said. A new value (a refetch, another viewer) resets the button. */
  initialLiked: boolean;
  initialCount: number;
  /** Called at once with the new state and count, and again with the old ones if the request fails. */
  onChange?: (liked: boolean, count: number) => void;
  /** Show the word "Like" from `sm` up (the post page); cards show the glyph and count only. */
  showLabel?: boolean;
  className?: string;
}

function Face({
  liked,
  count,
  showLabel,
}: {
  liked: boolean;
  count: number;
  showLabel: boolean;
}): ReactNode {
  return (
    <>
      <Icon
        name="favorite"
        size="lg"
        filled={liked}
        className={liked ? "text-secondary" : undefined}
      />
      {/* The name stays "Like <count>" in both states: `aria-pressed` says whether it is on. */}
      <span className="sr-only">{`Like ${formatCompactNumber(count)}`}</span>
      {showLabel && (
        <span aria-hidden="true" className="hidden sm:inline">
          Like
        </span>
      )}
      <span aria-hidden="true" className="tabular-nums">
        {formatCompactNumber(count)}
      </span>
    </>
  );
}

/**
 * Like / unlike (Stitch a1's `favorite_border`; liked = a filled glyph in `secondary`, ANALYSIS
 * b). The flip is optimistic: the glyph and count change first and go back, with a toast, if the
 * request fails. One request at a time, so a double click can't race itself. Visitors get a link to
 * log in; an unverified email gets an `aria-disabled` button that explains itself (Part 2's rule).
 * The count shown is the server's number moved by your own like, so someone else's like appears at
 * the next load.
 */
export function LikeButton({
  postId,
  initialLiked,
  initialCount,
  onChange,
  showLabel = false,
  className,
}: LikeButtonProps) {
  const { status, user } = useAuth();
  const toast = useToast();
  // One id per button: a feed of unverified viewers has many.
  const hintId = useId();
  const [state, setState] = useState({ liked: initialLiked, count: initialCount });
  const [seen, setSeen] = useState({ liked: initialLiked, count: initialCount });
  const inFlight = useRef(false);
  const { liked, count } = state;

  // The server's answer changed (a refetch, another viewer): follow it ("adjust state while rendering").
  if (seen.liked !== initialLiked || seen.count !== initialCount) {
    setSeen({ liked: initialLiked, count: initialCount });
    setState({ liked: initialLiked, count: initialCount });
  }

  const face = <Face liked={liked} count={count} showLabel={showLabel} />;
  const classes = cn(ACTION_CLASSES, className);

  if (status === "loading") {
    // Same size as the real button, nothing to click until we know who is asking.
    return <span className={cn(classes, "pointer-events-none")}>{face}</span>;
  }

  if (!user) {
    return (
      <Link href={loginRedirectFor(`/p/${postId}`)} prefetch={false} className={classes}>
        {face}
      </Link>
    );
  }

  if (!user.is_email_verified && !liked) {
    return (
      <>
        <button
          type="button"
          aria-disabled="true"
          aria-describedby={hintId}
          onClick={() => toast.show(SOCIAL_MESSAGES.verifyToLike)}
          className={cn(classes, "cursor-not-allowed opacity-60")}
        >
          {face}
        </button>
        <span id={hintId} className="sr-only">
          Verify your email to like posts.
        </span>
      </>
    );
  }

  async function toggle() {
    if (inFlight.current) return;
    inFlight.current = true;
    const next = !liked;
    const nextCount = Math.max(0, count + (next ? 1 : -1));
    setState({ liked: next, count: nextCount });
    onChange?.(next, nextCount);
    try {
      if (next) await likePost(postId);
      else await unlikePost(postId);
    } catch (error) {
      setState({ liked: !next, count });
      onChange?.(!next, count);
      toast.show(likeFailureMessage(error, !next), { tone: "error" });
    } finally {
      inFlight.current = false;
    }
  }

  return (
    <button type="button" aria-pressed={liked} onClick={() => void toggle()} className={classes}>
      {face}
    </button>
  );
}
