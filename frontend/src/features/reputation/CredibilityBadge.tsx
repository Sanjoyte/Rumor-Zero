import Link from "next/link";
import type { Reputation } from "@/lib/api/types";
import { formatCount } from "@/lib/format";

/** Where the score is explained (Part 15 built it: `features/info/CredibilitySection.tsx`). */
export const CREDIBILITY_HELP_HREF = "/how-it-works#credibility";
export const NEW_SCORE_HINT = "A score shows once 3 of their posts have been checked or removed.";

type Props =
  | { variant: "header"; reputation: Reputation }
  | { variant: "row"; reputation: Reputation; verified: number };

/**
 * An account's public credibility score (ARCHITECTURE §4a, §10): "Credibility 72", or "New" until
 * three of the person's posts have been checked or removed. **Neutral on purpose** (user decision
 * 2026-10-13): grey text and the neutral chip of Stitch c3, never the teal or the `verified` seal
 * that mark a verified fact. Shown in the profile header (c1's meta row, with the "How this is
 * calculated" link) and in follower/following rows (c3, with the verified count); never on a post
 * card. A Server Component: it only renders what the API sent.
 */
export function CredibilityBadge(props: Props) {
  const { score } = props.reputation;

  if (props.variant === "row") {
    return (
      <span className="flex flex-wrap items-center gap-x-space-sm gap-y-space-xs">
        <span
          className="rounded-lg border border-outline-variant/30 bg-surface-container px-space-xs py-0.5 font-label-badge text-label-badge text-on-surface-variant"
          title={score === null ? NEW_SCORE_HINT : undefined}
        >
          {score === null ? "Credibility: New" : `Credibility ${score}`}
        </span>
        <span className="font-label-badge text-label-badge font-medium text-on-surface-variant">
          · {formatCount(props.verified)} verified
        </span>
      </span>
    );
  }

  return (
    <span className="flex flex-wrap items-center gap-x-space-sm gap-y-space-xs">
      <span
        className="font-label-code text-label-code text-on-surface-variant"
        title={score === null ? NEW_SCORE_HINT : undefined}
      >
        {score === null ? "Credibility: New" : `Credibility ${score}`}
        {score === null && <span className="sr-only"> ({NEW_SCORE_HINT})</span>}
      </span>
      <Link
        href={CREDIBILITY_HELP_HREF}
        prefetch={false}
        className="font-medium text-secondary hover:underline"
      >
        How this is calculated
      </Link>
    </span>
  );
}
