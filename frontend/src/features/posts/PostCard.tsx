import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { Icon } from "@/components/ui/Icon";
import { AppealPendingBadge, EmergencyBadge, StatusBadge } from "@/components/ui/StatusBadge";
import { VerdictStripe } from "@/components/ui/VerdictStripe";
import { cn } from "@/lib/cn";
import { formatRelativeTime } from "@/lib/format";
import type { PostSource } from "@/lib/api/types";
import { type PostStatus, type PostType, type VerdictSource, stripeTone } from "@/lib/post-display";
import { SourceLink } from "./SourceLink";

export interface PostCardProps {
  author: { displayName: string; username: string; avatarUrl?: string | null };
  content: string;
  postType: PostType;
  status: PostStatus;
  /** API confidence_score, a decimal string such as "94.00" (pipeline verdicts only). */
  confidenceScore?: string | null;
  verdictSource?: VerdictSource | null;
  /** The API emergency_active flag: an emergency that is still pinned and live. */
  emergencyActive?: boolean;
  /** Shown to the author while an appeal is open. */
  appealPending?: boolean;
  /** A fact post's sources (§4c): the card shows the first one and "+N more". */
  sources?: PostSource[];
  createdAt: string | Date;
  /**
   * Where the card opens (`/p/{id}`, Part 5). The claim text becomes a stretched link, so the whole
   * card is clickable while the source links stay separate links above it. Without it the card is
   * inert (the gallery, previews).
   */
  href?: string;
  /** Clock for the relative timestamp; tests and the gallery pass a fixed one. */
  now?: Date;
  className?: string;
}

/**
 * Presentational post card (Stitch b1), with the one-line source row under a fact claim (Part 4).
 * Parts 7 and 7B add the action bar. A blank display name shows `@username` once, in bold.
 */
export function PostCard({
  author,
  content,
  postType,
  status,
  confidenceScore,
  verdictSource,
  emergencyActive = false,
  appealPending = false,
  sources = [],
  createdAt,
  href,
  now,
  className,
}: PostCardProps) {
  const time = formatRelativeTime(createdAt, now);
  const iso = createdAt instanceof Date ? createdAt.toISOString() : createdAt;

  if (status === "removed") {
    return (
      <Card as="article" className={cn("p-space-md font-body-sm text-body-sm", className)}>
        <div className="flex flex-wrap items-center justify-between gap-space-xs text-on-surface-variant">
          <p className="flex items-center gap-space-xs font-semibold">
            <Icon name="block" size="lg" className="text-outline" />
            Removed by a moderator
          </p>
          <time dateTime={iso} className="font-label-code text-label-code text-outline">
            {time}
          </time>
        </div>
      </Card>
    );
  }

  const tone = stripeTone({ status, emergencyActive });
  const hasName = author.displayName.trim() !== "";
  const name = hasName ? author.displayName : `@${author.username}`;

  return (
    <Card as="article" interactive className={className}>
      {tone && <VerdictStripe tone={tone} />}
      <div className="flex flex-col gap-space-md p-space-lg">
        <div className="flex flex-col gap-space-sm sm:flex-row sm:items-start sm:justify-between sm:gap-space-md">
          <div className="flex min-w-0 items-center gap-space-md">
            <Avatar name={name} src={author.avatarUrl} size={10} decorative />
            <div className="flex min-w-0 items-center gap-space-xs">
              <span className="min-w-0 truncate font-body-md text-body-md font-bold text-on-surface">
                {name}
              </span>
              {hasName && (
                <span className="min-w-0 truncate font-label-code text-label-code text-outline">
                  @{author.username}
                </span>
              )}
              <span aria-hidden="true" className="shrink-0 text-outline-variant">
                ·
              </span>
              <time
                dateTime={iso}
                className="shrink-0 font-label-code text-label-code text-outline"
              >
                {time}
              </time>
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-space-sm sm:justify-end">
            <CategoryChip type={postType} />
            <StatusBadge
              status={status}
              verdictSource={verdictSource}
              confidenceScore={confidenceScore}
            />
            {appealPending && <AppealPendingBadge />}
            {emergencyActive && <EmergencyBadge />}
          </div>
        </div>
        <blockquote
          className={cn(
            "leading-snug tracking-tight break-words whitespace-pre-wrap text-on-surface",
            postType === "fact"
              ? "font-claim-headline text-claim-headline"
              : "font-claim-opinion text-claim-opinion italic",
          )}
        >
          {href ? (
            // Not prefetched: every request is a Worker request (100k a day), and 20 cards would
            // prefetch 20 pages.
            <Link
              href={href}
              prefetch={false}
              className="after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-secondary/30"
            >
              {"\u201C"}
              {content}
              {"\u201D"}
            </Link>
          ) : (
            <>
              {"\u201C"}
              {content}
              {"\u201D"}
            </>
          )}
        </blockquote>
        {postType === "fact" && (
          <SourceLink sources={sources} moreHref={href ? `${href}#sources` : undefined} />
        )}
      </div>
    </Card>
  );
}
