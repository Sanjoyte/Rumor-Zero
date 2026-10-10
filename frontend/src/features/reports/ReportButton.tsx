"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { ACTION_CLASSES } from "@/features/social/LikeButton";
import { useAuth } from "@/lib/auth/AuthProvider";
import { loginRedirectFor } from "@/lib/auth/route-guard";
import { cn } from "@/lib/cn";
import { REPORT_MESSAGES } from "./messages";
import { ReportModal, type ReportedPost, type ReportOutcome } from "./ReportModal";

export interface ReportButtonProps {
  post: ReportedPost & { is_mine: boolean; reported_by_me: boolean };
  /** Show the word "Report" from `sm` up (the post page); cards show the flag glyph only. */
  showLabel?: boolean;
  className?: string;
}

const TOASTS: Record<ReportOutcome, string> = {
  sent: REPORT_MESSAGES.sent,
  already: REPORT_MESSAGES.already,
  gone: REPORT_MESSAGES.gone,
};

/**
 * The flag in the action bar (Stitch b1's `flag` beside the bookmark, b3's "Report"). It opens
 * `ReportModal`. One `<button>` throughout, so focus can come back to it after a report: it turns
 * into "You reported this" (a filled flag in `secondary`, `aria-disabled`) once the server has the
 * report, and the page can't report twice. No button on your own post; visitors get a link to log
 * in; an unverified email an `aria-disabled` button that explains itself (Part 2's rule). The
 * modal is built on the first click and then kept, so a feed doesn't carry 20 dialogs.
 */
export function ReportButton({ post, showLabel = false, className }: ReportButtonProps) {
  const { status, user } = useAuth();
  const toast = useToast();
  const hintId = useId();
  const [reported, setReported] = useState(post.reported_by_me);
  const [seen, setSeen] = useState(post.reported_by_me);
  const [open, setOpen] = useState(false);
  const [built, setBuilt] = useState(false);

  // The server's answer changed (a refetch, another viewer): follow it ("adjust state while rendering").
  if (seen !== post.reported_by_me) {
    setSeen(post.reported_by_me);
    setReported(post.reported_by_me);
  }

  // Your own post has no report action, even before the session has said who you are.
  if (post.is_mine || (user && user.id === post.author.id)) return null;

  const classes = cn(ACTION_CLASSES, className);
  const word = reported ? "Reported" : "Report";
  const face = (
    <>
      <Icon
        name="flag"
        size="lg"
        filled={reported}
        className={reported ? "text-secondary" : undefined}
      />
      {/* The visible word is part of the name ("Reported" ⊂ "You reported this"). */}
      <span className="sr-only">{reported ? "You reported this" : "Report"}</span>
      {showLabel && (
        <span aria-hidden="true" className="hidden sm:inline">
          {word}
        </span>
      )}
    </>
  );

  if (status === "loading") {
    // Same size as the real button, nothing to click until we know who is asking.
    return <span className={cn(classes, "pointer-events-none")}>{face}</span>;
  }

  if (!user) {
    return (
      <Link
        href={loginRedirectFor(`/p/${post.id}`)}
        prefetch={false}
        title={REPORT_MESSAGES.logIn}
        className={classes}
      >
        {face}
      </Link>
    );
  }

  const unverified = !user.is_email_verified && !reported;
  const hint = unverified ? REPORT_MESSAGES.verifyHint : null;
  const disabled = reported || unverified;

  function handleClick() {
    if (reported) return toast.show(REPORT_MESSAGES.already);
    if (unverified) return toast.show(REPORT_MESSAGES.verifyToast);
    setBuilt(true);
    setOpen(true);
  }

  function done(outcome: ReportOutcome) {
    setOpen(false);
    if (outcome !== "gone") setReported(true);
    toast.show(TOASTS[outcome]);
  }

  return (
    <>
      <button
        type="button"
        aria-disabled={disabled || undefined}
        aria-describedby={hint ? hintId : undefined}
        title={reported ? "You reported this" : (hint ?? "Report this post")}
        onClick={handleClick}
        className={cn(
          classes,
          // "You reported this" stays legible (it is a state, not a refusal); only a blocked
          // click, for an unverified email, is dimmed.
          reported && "cursor-default",
          unverified && "cursor-not-allowed opacity-60",
        )}
      >
        {face}
      </button>
      {hint && (
        <span id={hintId} className="sr-only">
          {hint}
        </span>
      )}
      {built && (
        <ReportModal open={open} post={post} onClose={() => setOpen(false)} onDone={done} />
      )}
    </>
  );
}
