"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";
import { EmergencyBadge, StatusBadge } from "@/components/ui/StatusBadge";
import { FollowButton } from "@/features/social/FollowButton";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/cn";
import type { NotificationData, NotificationType } from "@/lib/api/types";
import { actorName, NOTIFICATION_MESSAGES, notificationHref } from "./messages";

export interface NotificationItemProps {
  item: NotificationData;
  /** Read on the server, or marked read on this page since. */
  read: boolean;
  /** The item was opened (the link was followed): the list marks it read. */
  onOpen: (item: NotificationData) => void;
  /** The clock for "5m"; tests pass a fixed one. */
  now?: Date;
}

/** The glyph on the corner of the actor's avatar, and the verb the sentence uses. */
const ACTOR_KIND: Partial<Record<NotificationType, { glyph: string; badge: string }>> = {
  follow: { glyph: "person_add", badge: "bg-inverse-surface text-inverse-on-surface" },
  like: { glyph: "favorite", badge: "bg-inverse-surface text-inverse-on-surface" },
  comment: { glyph: "chat_bubble", badge: "bg-secondary text-on-secondary" },
  repost: { glyph: "repeat", badge: "bg-inverse-surface text-inverse-on-surface" },
};

/** Tile glyph and tone for the messages that come from the platform itself. */
function systemTile(item: NotificationData): { glyph: string; tone: string; filled?: boolean } {
  switch (item.type) {
    case "verdict":
      return item.outcome === "false"
        ? { glyph: "cancel", tone: "border-error/30 bg-error/10 text-error" }
        : { glyph: "verified", tone: "border-primary/30 bg-primary/10 text-primary", filled: true };
    case "under_review":
      return {
        glyph: "hourglass_top",
        tone: "border-verdict-review/30 bg-verdict-review/10 text-on-verdict-review",
      };
    case "emergency_demoted":
      return {
        glyph: "bolt",
        tone: "border-tertiary/30 bg-tertiary/10 text-tertiary",
        filled: true,
      };
    case "appeal_resolved":
      return {
        glyph: "gavel",
        tone: "border-outline-variant/30 bg-surface-container text-on-surface-variant",
      };
    default: // removed
      return {
        glyph: "block",
        tone: "border-outline-variant/30 bg-surface-container text-on-surface-variant",
      };
  }
}

function SystemTile({ item }: { item: NotificationData }) {
  const tile = systemTile(item);
  return (
    <div
      className={cn(
        "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border",
        tile.tone,
      )}
    >
      <Icon name={tile.glyph} size="xl" filled={tile.filled} />
    </div>
  );
}

function Quote({ text, postType }: { text: string; postType?: "fact" | "opinion" }) {
  return (
    <span
      className={cn(
        "break-words",
        postType === "opinion" ? "font-claim-opinion italic" : "font-claim-headline font-medium",
      )}
    >
      {"“"}
      {text}
      {"”"}
    </span>
  );
}

/** The sentence, and what sits under it, for each of the nine kinds. */
function describe(item: NotificationData): { text: ReactNode; extra: ReactNode } {
  const who = <span className="font-semibold">{actorName(item)}</span>;
  const post = item.post ? <Quote text={item.post.excerpt} postType={item.post.post_type} /> : null;
  switch (item.type) {
    case "follow":
      return { text: <>{who} followed you.</>, extra: null };
    case "like":
      return {
        text: (
          <>
            {who} liked your post {post}
          </>
        ),
        extra: null,
      };
    case "repost":
      return {
        text: (
          <>
            {who} reposted your post {post}
          </>
        ),
        extra: null,
      };
    case "comment":
      return {
        text: (
          <>
            {who} commented on your post {post}
          </>
        ),
        extra: item.comment && (
          <p className="mt-space-sm rounded-lg border-l-2 border-outline-variant bg-surface-container-low/70 py-space-xs pl-space-md font-claim-headline text-body-md break-words whitespace-pre-wrap text-on-surface-variant italic">
            {"“"}
            {item.comment.excerpt}
            {"”"}
          </p>
        ),
      };
    case "verdict": {
      const isFalse = item.outcome === "false";
      return {
        text: (
          <>
            Your fact post was checked and {isFalse ? "labelled FALSE" : "verified"}: {post}
          </>
        ),
        extra: (
          <div className="mt-space-sm flex flex-wrap items-center gap-space-sm">
            <StatusBadge status={isFalse ? "verified_false" : "verified_true"} />
          </div>
        ),
      };
    }
    case "under_review":
      return {
        text: <>Your post is under review. A moderator will look at it: {post}</>,
        extra: (
          <div className="mt-space-sm flex flex-wrap items-center gap-space-sm">
            <StatusBadge status="under_review" />
          </div>
        ),
      };
    case "removed":
      return {
        text: <>A moderator removed your post: {post}</>,
        extra: (
          <div className="mt-space-sm flex flex-wrap items-center gap-space-sm">
            <StatusBadge status="removed" />
            <span className="font-body-sm text-body-sm text-outline">
              The reason is on the post.
            </span>
          </div>
        ),
      };
    case "emergency_demoted":
      return {
        text: <>A moderator ended the priority of your emergency post early: {post}</>,
        extra: (
          <div className="mt-space-sm flex flex-wrap items-center gap-space-sm">
            <EmergencyBadge />
            <span className="font-body-sm text-body-sm text-outline">
              It is no longer pinned. It is still checked.
            </span>
          </div>
        ),
      };
    case "appeal_resolved": {
      const upheld = item.outcome === "upheld";
      return {
        text: (
          <>
            Your appeal was reviewed.{" "}
            {upheld ? "The decision stands" : "The decision was overturned"}: {post}
          </>
        ),
        extra: null,
      };
    }
  }
}

/**
 * One notification (Stitch c4): a tile or the actor's avatar, the sentence, a quote of the post,
 * the time and an unread dot. The whole row is the link (a stretched `::after` on the sentence's
 * link), so the Follow back button on a follow sits above it at `z-10` rather than inside it.
 * Moderation items name no moderator (ARCHITECTURE §2). Not built from c4: filter tabs, citation
 * and sensor-audit items, the sync row and the preferences link.
 */
export function NotificationItem({ item, read, onOpen, now }: NotificationItemProps) {
  const href = notificationHref(item);
  const { text, extra } = describe(item);
  const kind = ACTOR_KIND[item.type];
  const name = actorName(item);

  return (
    <article
      data-type={item.type}
      className="relative flex items-start gap-space-md px-space-md py-space-lg transition-colors hover:bg-surface-container-low/50"
    >
      {kind ? (
        <div className="relative mt-0.5 shrink-0">
          {item.actor ? (
            <Avatar name={name} src={item.actor.avatar_url} size={10} decorative />
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-outline-variant/40 bg-surface-container text-outline">
              <Icon name="person" size="xl" />
            </div>
          )}
          <span
            aria-hidden="true"
            className={cn(
              "absolute -right-1 -bottom-1 flex h-4 w-4 items-center justify-center rounded-full",
              kind.badge,
            )}
          >
            <Icon name={kind.glyph} size="xs" filled />
          </span>
        </div>
      ) : (
        <SystemTile item={item} />
      )}
      <div className="min-w-0 flex-1 pr-space-md">
        <p className="font-body-md text-body-md leading-snug text-on-surface">
          {href ? (
            <Link
              href={href}
              prefetch={false}
              onClick={() => onOpen(item)}
              className="after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-secondary/30 focus-visible:after:ring-inset"
            >
              {text}
            </Link>
          ) : (
            text
          )}
        </p>
        {extra}
        {item.type === "follow" && item.actor && (
          <div className="relative z-10 mt-space-sm flex items-center gap-space-md">
            <FollowButton
              username={item.actor.username}
              initialFollowing={Boolean(item.actor.following)}
              label={NOTIFICATION_MESSAGES.followBack}
              className="px-space-md py-space-xs"
            />
          </div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-space-sm pt-0.5">
        <time dateTime={item.created_at} className="font-label-code text-label-code text-outline">
          {formatRelativeTime(item.created_at, now)}
        </time>
        {!read && (
          <span className="h-1.5 w-1.5 rounded-full bg-secondary" title="Unread">
            <span className="sr-only">Unread</span>
          </span>
        )}
      </div>
    </article>
  );
}
