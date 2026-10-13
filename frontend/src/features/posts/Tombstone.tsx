import { Card } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";
import { formatRelativeTime } from "@/lib/format";

export const REMOVED_MESSAGES = {
  /** On a card, to anyone but the author. */
  card: "Removed by a moderator",
  /** On the post page, to anyone but the author (an e2e test and a unit test read it). */
  page: "This post was removed by a moderator.",
  onlyYou: "Only you can see this text.",
} as const;

/**
 * What everyone but the author sees of a removed post on a card (Stitch c1's tombstone, our `block`
 * glyph): no text, no author, no links, no badges. `PostCard` renders it for any removed post, so no
 * caller can ever show a removed post's words or action bar; `RemovedPostCard` is the author's own.
 */
export function Tombstone({
  createdAt,
  now,
  className,
}: {
  createdAt: string | Date;
  now?: Date;
  className?: string;
}) {
  const iso = createdAt instanceof Date ? createdAt.toISOString() : createdAt;
  return (
    <Card as="article" className={cn("p-space-md font-body-sm text-body-sm", className)}>
      <div className="flex flex-wrap items-center justify-between gap-space-xs text-on-surface-variant">
        <p className="flex items-center gap-space-xs font-semibold">
          <Icon name="block" size="lg" className="text-outline" />
          {REMOVED_MESSAGES.card}
        </p>
        <time dateTime={iso} className="font-label-code text-label-code text-outline">
          {formatRelativeTime(createdAt, now)}
        </time>
      </div>
    </Card>
  );
}
