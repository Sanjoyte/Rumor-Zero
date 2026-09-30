/**
 * Pure display rules for the stripe and status badge of a post (ARCHITECTURE section 4, "Badges").
 * Kept free of React so the whole badge table is unit-testable.
 */
import { formatConfidence } from "./format";

export type PostType = "opinion" | "fact";
export type PostStatus =
  "pending" | "published" | "verified_true" | "verified_false" | "under_review" | "removed";
export type VerdictSource = "pipeline" | "moderator";

export type StripeTone = "primary" | "error" | "verdict-review" | "tertiary" | "outline-variant";
export type BadgeTone = "primary" | "error" | "review" | "neutral-dashed" | "neutral";

export interface StatusBadgeSpec {
  label: string;
  glyph: string;
  tone: BadgeTone;
  spin?: boolean;
}

export interface PostDisplayInput {
  status: PostStatus;
  /** The API computes is_active_emergency at serialization time and sends it as emergency_active. */
  emergencyActive?: boolean;
  verdictSource?: VerdictSource | null;
  /** confidence_score is non-null only for pipeline verdicts. */
  confidenceScore?: string | number | null;
}

export const EMERGENCY_BADGE_SPEC = { label: "EMERGENCY", glyph: "bolt" } as const;

/** Colour of the 4px stripe, or null when the card has none (the removed tombstone). */
export function stripeTone({
  status,
  emergencyActive = false,
}: PostDisplayInput): StripeTone | null {
  if (status === "removed") return null;
  if (emergencyActive) return "tertiary";
  switch (status) {
    case "verified_true":
      return "primary";
    case "verified_false":
      return "error";
    case "under_review":
      return "verdict-review";
    default:
      return "outline-variant"; // opinion (published) and pending
  }
}

function verdictLabel(word: string, input: PostDisplayInput): string {
  if (input.verdictSource === "moderator") return `${word} · REVIEWED`;
  const pct = input.verdictSource === "pipeline" ? formatConfidence(input.confidenceScore) : "";
  return pct ? `${word} ${pct}` : word;
}

/** The status badge for a post, or null when none is shown (a published opinion). */
export function statusBadgeSpec(input: PostDisplayInput): StatusBadgeSpec | null {
  switch (input.status) {
    case "pending":
      return {
        label: "CHECKING FACTS…",
        glyph: "progress_activity",
        tone: "neutral-dashed",
        spin: true,
      };
    case "published":
      return null;
    case "verified_true":
      return { label: verdictLabel("VERIFIED", input), glyph: "check_circle", tone: "primary" };
    case "verified_false":
      return { label: verdictLabel("FALSE", input), glyph: "cancel", tone: "error" };
    case "under_review":
      return { label: "UNDER REVIEW", glyph: "hourglass_top", tone: "review" };
    case "removed":
      return { label: "REMOVED", glyph: "block", tone: "neutral" };
  }
}
