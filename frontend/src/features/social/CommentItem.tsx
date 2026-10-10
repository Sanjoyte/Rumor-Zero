import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import type { Comment } from "@/lib/api/types";
import { formatFullDateTime, formatRelativeTime } from "@/lib/format";

/**
 * One comment (Stitch b3's row, flat: no Reply, id, role chip or likes). The text is plain
 * (`whitespace-pre-wrap`, never HTML). "Delete" shows only on your own.
 */
export function CommentItem({
  comment,
  onDelete,
  now,
}: {
  comment: Comment;
  onDelete?: (comment: Comment) => void;
  /** Clock for the relative time; tests pass a fixed one. */
  now?: Date;
}) {
  const { author } = comment;
  const hasName = author.display_name.trim() !== "";
  const name = hasName ? author.display_name : `@${author.username}`;
  return (
    <Card as="article" className="flex flex-col gap-space-xs p-space-lg">
      <div className="flex flex-wrap items-center justify-between gap-x-space-md gap-y-space-xs">
        <Link
          href={`/u/${author.username}`}
          prefetch={false}
          className="group flex min-w-0 items-center gap-space-sm rounded-lg focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none"
        >
          <Avatar name={name} src={author.avatar_url} size={8} decorative />
          <span className="min-w-0 truncate font-body-md text-body-md font-semibold text-on-surface group-hover:underline">
            {name}
          </span>
          {hasName && (
            <span className="min-w-0 truncate font-label-code text-label-code text-outline">
              @{author.username}
            </span>
          )}
        </Link>
        <time
          dateTime={comment.created_at}
          title={formatFullDateTime(comment.created_at)}
          className="shrink-0 font-label-code text-label-code text-outline"
        >
          {formatRelativeTime(comment.created_at, now)}
        </time>
      </div>
      <p className="pt-space-xs font-body-md text-body-md break-words whitespace-pre-wrap text-on-surface">
        {comment.content}
      </p>
      {comment.is_mine && onDelete && (
        <button
          type="button"
          onClick={() => onDelete(comment)}
          className="self-start rounded-lg font-label-code text-label-code font-semibold text-outline uppercase transition-colors hover:text-on-surface focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none"
        >
          Delete
        </button>
      )}
    </Card>
  );
}
