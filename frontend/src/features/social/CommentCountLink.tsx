import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";
import { formatCompactNumber } from "@/lib/format";
import { ACTION_CLASSES } from "./LikeButton";

/**
 * The comment glyph and count in the action bar (Stitch b1/a1's `chat_bubble_outline`). It is a link:
 * from a card to the post's discussion, on the post page to the section below.
 */
export function CommentCountLink({
  href,
  count,
  showLabel = false,
  className,
}: {
  href: string;
  count: number;
  showLabel?: boolean;
  className?: string;
}) {
  return (
    <Link href={href} prefetch={false} className={cn(ACTION_CLASSES, className)}>
      <Icon name="chat_bubble" size="lg" />
      <span className="sr-only">{`Comments ${formatCompactNumber(count)}`}</span>
      {showLabel && (
        <span aria-hidden="true" className="hidden sm:inline">
          Comments
        </span>
      )}
      <span aria-hidden="true" className="tabular-nums">
        {formatCompactNumber(count)}
      </span>
    </Link>
  );
}
