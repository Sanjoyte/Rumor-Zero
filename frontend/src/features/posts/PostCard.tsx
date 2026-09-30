import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { Icon } from "@/components/ui/Icon";
import { AppealPendingBadge, EmergencyBadge, StatusBadge } from "@/components/ui/StatusBadge";
import { VerdictStripe } from "@/components/ui/VerdictStripe";
import { cn } from "@/lib/cn";
import { formatRelativeTime } from "@/lib/format";
import { type PostStatus, type PostType, type VerdictSource, stripeTone } from "@/lib/post-display";

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
  createdAt: string | Date;
  /** Clock for the relative timestamp; tests and the gallery pass a fixed one. */
  now?: Date;
  className?: string;
}

/**
 * Presentational post card (Stitch b1). Part 4 feeds it real data and adds the source line;
 * Parts 7 and 7B add the action bar.
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
  createdAt,
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

  return (
    <Card as="article" interactive className={className}>
      {tone && <VerdictStripe tone={tone} />}
      <div className="flex flex-col gap-space-md p-space-lg">
        <div className="flex items-start justify-between gap-space-md">
          <div className="flex min-w-0 items-center gap-space-md">
            <Avatar name={author.displayName} src={author.avatarUrl} size={10} decorative />
            <div className="flex min-w-0 flex-wrap items-center gap-space-xs">
              <span className="font-body-md text-body-md font-bold text-on-surface">
                {author.displayName}
              </span>
              <span className="font-label-code text-label-code text-outline">
                @{author.username}
              </span>
              <span aria-hidden="true" className="text-outline-variant">
                ·
              </span>
              <time dateTime={iso} className="font-label-code text-label-code text-outline">
                {time}
              </time>
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-space-sm">
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
          {"\u201C"}
          {content}
          {"\u201D"}
        </blockquote>
      </div>
    </Card>
  );
}
