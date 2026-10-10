"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth/AuthProvider";
import { loginRedirectFor } from "@/lib/auth/route-guard";
import { cn } from "@/lib/cn";
import { ACTION_CLASSES } from "./LikeButton";
import { bookmarkFailureMessage } from "./messages";
import { bookmarkPost, unbookmarkPost } from "./social-api";

export interface BookmarkButtonProps {
  postId: string;
  /** What the server said. A new value (a refetch) resets the button. */
  initialBookmarked: boolean;
  className?: string;
}

/**
 * Save / unsave (Stitch's `bookmark_border`; saved = a filled `bookmark` in `secondary`, ANALYSIS
 * f-4). Bookmarks are private, so there is no count and no verified-email rule: any signed-in
 * user can use it. The flip is optimistic and goes back, with a toast, if the request fails; one
 * request at a time. Visitors get a link to log in.
 */
export function BookmarkButton({ postId, initialBookmarked, className }: BookmarkButtonProps) {
  const { status, user } = useAuth();
  const toast = useToast();
  const [saved, setSaved] = useState(initialBookmarked);
  const [seen, setSeen] = useState(initialBookmarked);
  const inFlight = useRef(false);

  // The server's answer changed (a refetch): follow it ("adjust state while rendering").
  if (seen !== initialBookmarked) {
    setSeen(initialBookmarked);
    setSaved(initialBookmarked);
  }

  const face = (
    <>
      <Icon
        name="bookmark"
        size="lg"
        filled={saved}
        className={saved ? "text-secondary" : undefined}
      />
      <span className="sr-only">Bookmark</span>
    </>
  );
  const classes = cn(ACTION_CLASSES, className);

  if (status === "loading") {
    return <span className={cn(classes, "pointer-events-none")}>{face}</span>;
  }

  if (!user) {
    return (
      <Link href={loginRedirectFor(`/p/${postId}`)} prefetch={false} className={classes}>
        {face}
      </Link>
    );
  }

  async function toggle() {
    if (inFlight.current) return;
    inFlight.current = true;
    const next = !saved;
    setSaved(next);
    try {
      if (next) await bookmarkPost(postId);
      else await unbookmarkPost(postId);
    } catch (error) {
      setSaved(!next);
      toast.show(bookmarkFailureMessage(error, !next), { tone: "error" });
    } finally {
      inFlight.current = false;
    }
  }

  return (
    <button
      type="button"
      aria-pressed={saved}
      title={saved ? "Remove bookmark" : "Bookmark"}
      onClick={() => void toggle()}
      className={classes}
    >
      {face}
    </button>
  );
}
