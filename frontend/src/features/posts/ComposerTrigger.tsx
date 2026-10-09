"use client";

import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { buttonClasses } from "@/components/ui/Button";
import { NEW_POST_BLOCKED_HINT } from "@/components/shell/nav-items";
import { useAuth } from "@/lib/auth/AuthProvider";
import { loginRedirectFor } from "@/lib/auth/route-guard";
import { cn } from "@/lib/cn";
import { useComposer } from "./ComposerProvider";

const HINT_ID = "composer-trigger-hint";

/**
 * Stitch b1's inline composer, as a trigger that opens the modal (the b2 composer): a card that
 * looks like a text box. Unverified users get an `aria-disabled` card and the same toast as the
 * "New post" button (Part 2's rule); visitors get "Log in to post"; while the session loads it is
 * a skeleton of the same size.
 */
export function ComposerTrigger({ className }: { className?: string }) {
  const { status, user } = useAuth();
  const composer = useComposer();

  if (status === "loading") return <Skeleton className={cn("h-[4.25rem] w-full", className)} />;

  if (status === "anonymous" || !user) {
    return (
      <Card className={cn("flex items-center justify-between gap-space-md p-space-md", className)}>
        <p className="font-body-md text-body-md text-on-surface-variant">
          Log in to share an opinion or a fact.
        </p>
        <Link
          href={loginRedirectFor("/home")}
          className={buttonClasses({ variant: "primary", className: "shrink-0" })}
        >
          Log in to post
        </Link>
      </Card>
    );
  }

  const blocked = !user.is_email_verified;
  return (
    <Card className={cn("p-space-md", className)}>
      <button
        type="button"
        onClick={composer.open}
        aria-disabled={blocked || undefined}
        aria-describedby={blocked ? HINT_ID : undefined}
        className={cn(
          "flex w-full items-center gap-space-md rounded-lg text-left",
          blocked && "cursor-not-allowed opacity-60",
        )}
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-container-high text-on-surface-variant">
          <Icon name="edit_note" size="lg" />
        </span>
        <span className="min-w-0 flex-1 truncate font-claim-headline text-body-md text-outline">
          What do you want to say?
        </span>
        <span
          aria-hidden="true"
          className="hidden shrink-0 rounded-lg bg-secondary px-space-md py-space-xs font-body-md text-body-md font-semibold text-on-secondary shadow-sm sm:block"
        >
          New post
        </span>
      </button>
      {blocked && (
        <span id={HINT_ID} className="sr-only">
          {NEW_POST_BLOCKED_HINT}
        </span>
      )}
    </Card>
  );
}
