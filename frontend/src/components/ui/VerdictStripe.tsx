import { cn } from "@/lib/cn";
import type { StripeTone } from "@/lib/post-display";

export type VerdictStripeTone = StripeTone | "inverse-surface";

const TONE: Record<VerdictStripeTone, string> = {
  primary: "bg-primary",
  error: "bg-error",
  "verdict-review": "bg-verdict-review",
  tertiary: "bg-tertiary",
  "outline-variant": "bg-outline-variant",
  // Quoted-post preview inside the report modal (Stitch d1).
  "inverse-surface": "bg-inverse-surface",
};

/** The 4px band on the left edge of a card. Put it inside a relative, overflow-hidden parent. */
export function VerdictStripe({
  tone,
  className,
}: {
  tone: VerdictStripeTone;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      data-tone={tone}
      className={cn("absolute top-0 bottom-0 left-0 w-1", TONE[tone], className)}
    />
  );
}
