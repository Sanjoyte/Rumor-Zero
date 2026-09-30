import { cn } from "@/lib/cn";
import {
  type BadgeTone,
  EMERGENCY_BADGE_SPEC,
  type PostDisplayInput,
  statusBadgeSpec,
} from "@/lib/post-display";
import { Icon } from "./Icon";

const BASE =
  "inline-flex items-center gap-space-xs rounded-lg border px-space-sm py-0.5 font-label-code text-label-code font-bold uppercase";

const TONE: Record<BadgeTone | "tertiary", string> = {
  primary: "border-primary/30 bg-primary/10 text-primary",
  error: "border-error/30 bg-error/10 text-error",
  review: "border-verdict-review/30 bg-verdict-review/10 text-on-verdict-review",
  tertiary: "border-tertiary/30 bg-tertiary/10 text-tertiary",
  "neutral-dashed": "border-dashed border-outline-variant bg-surface-container-low text-outline",
  neutral: "border-outline-variant bg-surface-container text-outline",
};

/**
 * The status of a post as glyph + label (+ percentage for pipeline verdicts), never colour alone.
 * Renders nothing for a published opinion, which shows only its OPINION chip.
 */
export function StatusBadge({ className, ...input }: PostDisplayInput & { className?: string }) {
  const spec = statusBadgeSpec(input);
  if (!spec) return null;
  return (
    <span className={cn(BASE, TONE[spec.tone], className)}>
      <Icon
        name={spec.glyph}
        className={spec.spin ? "animate-spin motion-reduce:animate-none" : undefined}
      />
      {spec.label}
    </span>
  );
}

/** The violet chip shown next to the status badge while an emergency is active. */
export function EmergencyBadge({ className }: { className?: string }) {
  return (
    <span className={cn(BASE, TONE.tertiary, className)}>
      <Icon name={EMERGENCY_BADGE_SPEC.glyph} size="sm" filled />
      {EMERGENCY_BADGE_SPEC.label}
    </span>
  );
}

/** Amber chip for the author while an appeal is open (ANALYSIS b-2). */
export function AppealPendingBadge({ className }: { className?: string }) {
  return (
    <span className={cn(BASE, TONE.review, className)}>
      <Icon name="gavel" size="sm" />
      APPEAL PENDING
    </span>
  );
}
