import { cn } from "@/lib/cn";

/** A grey placeholder block for content that is still loading. Size it with className. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded-lg bg-surface-container motion-reduce:animate-none",
        className,
      )}
    />
  );
}
