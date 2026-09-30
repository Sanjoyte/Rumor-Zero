import { cn } from "@/lib/cn";
import type { PostType } from "@/lib/post-display";

const LABEL: Record<PostType, string> = { fact: "FACT", opinion: "OPINION" };

/** The neutral FACT or OPINION tag on a post (Stitch b1). Never coloured: colour is for verdicts. */
export function CategoryChip({ type, className }: { type: PostType; className?: string }) {
  return (
    <span
      className={cn(
        "rounded-lg border border-outline-variant/30 bg-surface-container-low px-space-sm py-0.5 font-label-code text-label-code text-outline uppercase",
        className,
      )}
    >
      {LABEL[type]}
    </span>
  );
}
