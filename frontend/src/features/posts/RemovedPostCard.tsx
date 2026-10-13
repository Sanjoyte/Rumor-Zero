"use client";

import Link from "next/link";
import { type ReactNode, useState } from "react";
import { Card } from "@/components/ui/Card";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { Icon } from "@/components/ui/Icon";
import { AppealPendingBadge } from "@/components/ui/StatusBadge";
import { AppealButton } from "@/features/appeals/AppealButton";
import { AppealOutcome } from "@/features/appeals/AppealOutcome";
import type { Post } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatRelativeTime } from "@/lib/format";
import { REMOVED_MESSAGES, Tombstone } from "./Tombstone";

export interface RemovedPostCardProps {
  post: Post;
  /** "card" is a feed item (links to the post); "page" is `/p/[id]` (the claim is its `<h1>`). */
  layout?: "card" | "page";
  /** Page layout: the author row (a link to their profile; the author is public even when removed). */
  authorRow?: ReactNode;
  /** Page layout, author variant: something at the bottom of the card (Delete). */
  footer?: ReactNode;
  /** An appeal was sent: the post as it now stands (the page patches itself with it). */
  onFiled?: (post: Post) => void;
  /** The server says it can't be appealed any more: the page refetches the post. */
  onStale?: () => void;
  now?: Date;
  className?: string;
}

/**
 * A removed post (ARCHITECTURE §3, §9; Stitch c1's tombstone). **Everyone but its author** sees
 * the tombstone: no text, no badges, nothing to open. **The author** sees their own words marked
 * "Only you can see this text.", the reason a moderator gave (if any), and their appeal: the
 * "Request another look" button, then the APPEAL PENDING chip and what became of it. Their words
 * are quoted in the card's claim fonts, never as HTML.
 *
 * A request that went through is kept here (`filed`), so the chip and the outcome stay when the
 * list builds a new post object on its next poll, until the server's own copy knows the status.
 */
export function RemovedPostCard({
  post,
  layout = "card",
  authorRow,
  footer,
  onFiled,
  onStale,
  now,
  className,
}: RemovedPostCardProps) {
  const [filed, setFiled] = useState<Post | null>(null);
  // After "already appealed" or "can't be appealed" the button is gone until the server says more.
  const [stale, setStale] = useState(false);

  if (!post.is_mine) {
    if (layout === "card")
      return <Tombstone createdAt={post.created_at} now={now} className={className} />;
    return (
      <Card as="article" className={cn("flex flex-col gap-space-lg p-space-xl", className)}>
        {authorRow}
        <p className="flex items-center gap-space-xs font-body-md text-body-md font-semibold text-on-surface-variant">
          <Icon name="block" size="xl" className="text-outline" />
          {REMOVED_MESSAGES.page}
        </p>
      </Card>
    );
  }

  const shown = filed && filed.id === post.id && post.appeal_status === null ? filed : post;
  const canAppeal = shown.can_appeal && !stale;
  const reason = shown.removal_reason.trim();
  const isFact = shown.post_type === "fact";
  const page = layout === "page";
  const claimClasses = cn(
    "break-words whitespace-pre-wrap text-on-surface",
    page ? "text-headline-md leading-tight tracking-tight" : "leading-snug tracking-tight",
    isFact
      ? page
        ? "font-claim-headline"
        : "font-claim-headline text-claim-headline"
      : page
        ? "font-claim-opinion italic"
        : "font-claim-opinion text-claim-opinion italic",
  );
  const claim = (
    <>
      {"“"}
      {shown.content}
      {"”"}
    </>
  );

  function filedAppeal(updated: Post) {
    setFiled(updated);
    onFiled?.(updated);
  }
  function staleAppeal() {
    setStale(true);
    onStale?.();
  }

  const appealArea = (
    <div className="flex flex-col gap-space-sm">
      <AppealOutcome post={shown} />
      {canAppeal && (
        <div className="flex">
          <AppealButton
            post={{ ...shown, can_appeal: canAppeal }}
            onFiled={filedAppeal}
            onStale={staleAppeal}
          />
        </div>
      )}
    </div>
  );
  const details = (
    <>
      <p className="font-label-code text-label-code text-outline">{REMOVED_MESSAGES.onlyYou}</p>
      {reason && (
        <p className="font-body-sm text-body-sm break-words whitespace-pre-wrap text-on-surface-variant">
          Reason given: {reason}
        </p>
      )}
    </>
  );

  if (page) {
    return (
      <Card as="article" className={cn("flex flex-col gap-space-lg p-space-xl", className)}>
        <div className="flex flex-wrap items-center gap-space-sm">
          <CategoryChip type={shown.post_type} />
          <span className="inline-flex items-center gap-space-xs rounded-lg border border-outline-variant bg-surface-container px-space-sm py-0.5 font-label-code text-label-code font-bold text-outline uppercase">
            <Icon name="block" />
            Removed
          </span>
          {shown.appeal_status === "open" && <AppealPendingBadge />}
        </div>
        <h1 className={claimClasses}>{claim}</h1>
        <div className="flex flex-col gap-space-xs">{details}</div>
        {authorRow}
        {appealArea}
        {footer && (
          <div className="flex flex-wrap items-center gap-x-space-lg gap-y-space-sm border-t border-outline-variant/30 pt-space-md">
            {footer}
          </div>
        )}
      </Card>
    );
  }

  return (
    <Card
      as="article"
      className={cn("flex flex-col gap-space-sm p-space-md font-body-sm text-body-sm", className)}
    >
      <div className="flex flex-wrap items-center justify-between gap-space-xs text-on-surface-variant">
        <p className="flex items-center gap-space-xs font-semibold">
          <Icon name="block" size="lg" className="text-outline" />
          {REMOVED_MESSAGES.card}
        </p>
        <div className="flex flex-wrap items-center gap-space-sm">
          {shown.appeal_status === "open" && <AppealPendingBadge />}
          <time
            dateTime={shown.created_at}
            className="font-label-code text-label-code text-outline"
          >
            {formatRelativeTime(shown.created_at, now)}
          </time>
        </div>
      </div>
      {details}
      <blockquote className={claimClasses}>
        <Link
          href={`/p/${shown.id}`}
          prefetch={false}
          className="rounded-lg focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none"
        >
          {claim}
        </Link>
      </blockquote>
      {appealArea}
    </Card>
  );
}
