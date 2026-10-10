import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";
import type { UserSummary } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { RepostHeader } from "./RepostHeader";

/**
 * A repost whose original was deleted or removed (ARCHITECTURE §4d, §9): the repost stays, the text
 * doesn't. It borrows the removed-post tombstone's look. When the repost is yours, "Undo repost"
 * clears it from your profile and your followers' feeds (user decision 2026-10-10).
 */
export function UnavailablePostCard({
  reposter,
  onUndo,
  undoing = false,
  className,
}: {
  reposter: UserSummary;
  /** Given only for your own repost. */
  onUndo?: () => void;
  undoing?: boolean;
  className?: string;
}) {
  return (
    <Card as="article" className={cn("p-space-md font-body-sm text-body-sm", className)}>
      <div className="flex flex-col gap-space-sm">
        <RepostHeader user={reposter} />
        <div className="flex flex-wrap items-center justify-between gap-space-xs text-on-surface-variant">
          <p className="flex items-center gap-space-xs font-semibold">
            <Icon name="block" size="lg" className="text-outline" />
            This post is no longer available
          </p>
          {onUndo && (
            <Button variant="ghost" onClick={onUndo} loading={undoing}>
              Undo repost
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
