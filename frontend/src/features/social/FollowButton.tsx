"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Button, buttonClasses } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth/AuthProvider";
import { loginRedirectFor } from "@/lib/auth/route-guard";
import { cn } from "@/lib/cn";
import { followFailureMessage, SOCIAL_MESSAGES } from "./messages";
import { followUser, unfollowUser } from "./social-api";

const HINT_ID = "follow-hint";

export interface FollowButtonProps {
  username: string;
  /** What the server said. A new value (a refetch, another viewer) resets the button. */
  initialFollowing: boolean;
  /** Called at once with the new state, and again with the old one if the request fails. */
  onChange?: (following: boolean) => void;
  /** The idle word, "Follow" unless a screen says better ("Follow back" under a new follower). */
  label?: string;
  className?: string;
}

/**
 * Follow (primary) / Following (secondary; hover says "Unfollow"), Stitch c3. The flip is
 * optimistic: the button changes first and goes back, with a toast, if the request fails. One
 * request at a time, so a double click can't race itself. Visitors get a link to log in; an
 * unverified email gets an `aria-disabled` button that explains itself (Part 2's rule). Never
 * rendered for your own account: the callers show "Edit profile" instead.
 */
export function FollowButton({
  username,
  initialFollowing,
  onChange,
  label = "Follow",
  className,
}: FollowButtonProps) {
  const { status, user } = useAuth();
  const toast = useToast();
  const [following, setFollowing] = useState(initialFollowing);
  const [seen, setSeen] = useState(initialFollowing);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);

  // The server's answer changed (a refetch, another viewer): follow it ("adjust state while rendering").
  if (seen !== initialFollowing) {
    setSeen(initialFollowing);
    setFollowing(initialFollowing);
  }

  if (status === "loading") {
    return <span aria-hidden="true" className={cn("inline-block h-10 w-24", className)} />;
  }

  if (status === "anonymous" || !user) {
    return (
      <Link
        href={loginRedirectFor(`/u/${username}`)}
        className={buttonClasses({ variant: "primary", className })}
      >
        {label}
      </Link>
    );
  }

  if (!user.is_email_verified && !following) {
    return (
      <>
        <button
          type="button"
          aria-disabled="true"
          aria-describedby={HINT_ID}
          onClick={() => toast.show(SOCIAL_MESSAGES.verifyToFollow)}
          className={buttonClasses({
            variant: "primary",
            className: cn("cursor-not-allowed opacity-60", className),
          })}
        >
          {label}
        </button>
        <span id={HINT_ID} className="sr-only">
          Verify your email to follow people.
        </span>
      </>
    );
  }

  async function toggle() {
    if (inFlight.current) return;
    inFlight.current = true;
    const next = !following;
    setBusy(true);
    setFollowing(next);
    onChange?.(next);
    try {
      if (next) await followUser(username);
      else await unfollowUser(username);
    } catch (error) {
      setFollowing(!next);
      onChange?.(!next);
      toast.show(followFailureMessage(error, !next), { tone: "error" });
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <Button
      variant={following ? "secondary" : "primary"}
      loading={busy}
      onClick={toggle}
      title={following ? `Unfollow @${username}` : undefined}
      className={cn("group", className)}
    >
      {following ? (
        // Both words share one cell and only their opacity changes, so the accessible name stays
        // "Following" under the pointer (a hidden span would drop out of it) and the width is fixed.
        <span className="grid">
          <span className="col-start-1 row-start-1 group-hover:opacity-0 group-focus-visible:opacity-0">
            Following
          </span>
          <span
            aria-hidden="true"
            className="col-start-1 row-start-1 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"
          >
            Unfollow
          </span>
        </span>
      ) : (
        label
      )}
    </Button>
  );
}
