import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Button } from "./Button";
import { Icon } from "./Icon";

export interface LoadMoreProps {
  /** False shows the end-of-list note instead of the button. */
  hasMore: boolean;
  loading?: boolean;
  onClick: () => void;
  /** Shown when there is nothing more to load. */
  endLabel?: ReactNode;
  className?: string;
}

/** Cursor-pagination control under a list (Stitch b4). */
export function LoadMore({
  hasMore,
  loading,
  onClick,
  endLabel = "You have reached the end.",
  className,
}: LoadMoreProps) {
  return (
    <div className={cn("flex flex-col items-center gap-space-md pt-space-md pb-12", className)}>
      {hasMore ? (
        <Button variant="secondary" loading={loading} onClick={onClick}>
          {!loading && <Icon name="expand_more" size="sm" className="text-outline" />}
          {loading ? "Loading…" : "Load more"}
        </Button>
      ) : (
        <p className="flex items-center gap-space-xs font-label-code text-label-badge text-outline">
          <span
            aria-hidden="true"
            className="inline-block h-1.5 w-1.5 rounded-full bg-outline-variant"
          />
          {endLabel}
        </p>
      )}
    </div>
  );
}
