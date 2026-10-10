"use client";

import Link from "next/link";
import { type ReactNode, useId, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth/AuthProvider";
import { loginRedirectFor } from "@/lib/auth/route-guard";
import { cn } from "@/lib/cn";
import { formatCompactNumber } from "@/lib/format";
import { ACTION_CLASSES } from "./LikeButton";
import { repostFailureMessage, SOCIAL_MESSAGES } from "./messages";
import { repostPost, unrepostPost } from "./social-api";

export interface RepostButtonProps {
  postId: string;
  /** What the server said. A new value (a refetch, another viewer) resets the button. */
  initialReposted: boolean;
  initialCount: number;
  /**
   * Why this post can't be reposted (your own, FALSE or removed), from `repostBlockedReason`.
   * The button is then disabled and says so, unless you already reposted it: you can always
   * take a repost back.
   */
  blockedReason?: string | null;
  /** Show the word "Repost" from `sm` up (the post page); cards show the glyph and count only. */
  showLabel?: boolean;
  className?: string;
}

function Face({
  reposted,
  count,
  showLabel,
}: {
  reposted: boolean;
  count: number;
  showLabel: boolean;
}): ReactNode {
  return (
    <>
      <Icon name="cached" size="lg" className={reposted ? "text-secondary" : undefined} />
      {/* The name stays "Repost <count>" in both states: `aria-pressed` says whether it is on. */}
      <span className="sr-only">{`Repost ${formatCompactNumber(count)}`}</span>
      {showLabel && (
        <span aria-hidden="true" className="hidden sm:inline">
          Repost
        </span>
      )}
      <span aria-hidden="true" className="tabular-nums">
        {formatCompactNumber(count)}
      </span>
    </>
  );
}

/**
 * Repost / undo (Stitch b1/b3's `cached` counter, "Citations" renamed "Reposts", ANALYSIS f-4;
 * reposted = `secondary`). Like `LikeButton`: the flip is optimistic and goes back, with a toast,
 * if the request fails; one request at a time; visitors get a link to log in. Unlike a like it
 * can be refused for a reason the button knows in advance (`blockedReason`), and an unverified
 * email may only take a repost back. A repost shows the original's live label: reposting never
 * copies a status.
 */
export function RepostButton({
  postId,
  initialReposted,
  initialCount,
  blockedReason = null,
  showLabel = false,
  className,
}: RepostButtonProps) {
  const { status, user } = useAuth();
  const toast = useToast();
  const hintId = useId();
  const [state, setState] = useState({ reposted: initialReposted, count: initialCount });
  const [seen, setSeen] = useState({ reposted: initialReposted, count: initialCount });
  const inFlight = useRef(false);
  const { reposted, count } = state;

  // The server's answer changed (a refetch, another viewer): follow it ("adjust state while rendering").
  if (seen.reposted !== initialReposted || seen.count !== initialCount) {
    setSeen({ reposted: initialReposted, count: initialCount });
    setState({ reposted: initialReposted, count: initialCount });
  }

  const face = <Face reposted={reposted} count={count} showLabel={showLabel} />;
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

  // Nothing to explain when you can take your own repost back. The hint is short; the toast that
  // a click shows says more (as `LikeButton` does).
  let refusal: { hint: string; toast: string } | null = null;
  if (!reposted) {
    if (blockedReason) refusal = { hint: blockedReason, toast: blockedReason };
    else if (!user.is_email_verified) {
      refusal = {
        hint: "Verify your email to repost posts.",
        toast: SOCIAL_MESSAGES.verifyToRepost,
      };
    }
  }
  if (refusal) {
    const { hint, toast: message } = refusal;
    return (
      <>
        <button
          type="button"
          aria-disabled="true"
          aria-describedby={hintId}
          title={hint}
          onClick={() => toast.show(message)}
          className={cn(classes, "cursor-not-allowed opacity-60")}
        >
          {face}
        </button>
        <span id={hintId} className="sr-only">
          {hint}
        </span>
      </>
    );
  }

  async function toggle() {
    if (inFlight.current) return;
    inFlight.current = true;
    const next = !reposted;
    const nextCount = Math.max(0, count + (next ? 1 : -1));
    setState({ reposted: next, count: nextCount });
    try {
      if (next) await repostPost(postId);
      else await unrepostPost(postId);
    } catch (error) {
      setState({ reposted: !next, count });
      toast.show(repostFailureMessage(error, !next), { tone: "error" });
    } finally {
      inFlight.current = false;
    }
  }

  return (
    <button type="button" aria-pressed={reposted} onClick={() => void toggle()} className={classes}>
      {face}
    </button>
  );
}
