/**
 * What the composer says about emergency posts (ARCHITECTURE §4b, Part 11C): why the toggle is off,
 * the warning, the confirmation. Plain words (D8): no "bypass", no "permanent marker".
 */
import type { EmergencyEligibility } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { formatNextSlot } from "./quota";

export const EMERGENCY_COPY = {
  title: "Emergency",
  description: "Pinned at the top of feeds and checked before other posts.",
  toggleLabel: "Emergency post",
  warningTitle: "Emergency post",
  warning: "Use this only for urgent safety or public-health news.",
  confirmError: "Tick the box to confirm.",
  posted: "Posted. It's pinned while it's checked.",
  submit: "Post emergency, will be checked",
} as const;

/** The confirmation sentence, with the real block length (none at 0 days). */
export function confirmationText(blockDays: number): string {
  const block =
    blockDays > 0
      ? `, and misuse lowers my credibility score and blocks emergency posting for ${blockDays} ${
          blockDays === 1 ? "day" : "days"
        }`
      : ", and misuse lowers my credibility score";
  return `I understand emergency posts are checked first${block}.`;
}

interface Options {
  now?: Date;
  /** IANA zone; the viewer's own by default. Tests pass "UTC". */
  timeZone?: string;
}

/** "Next at 14:05" / "Next tomorrow at 02:10": a slot inside the next 24 hours. */
function nextSlot(iso: string, options: Options): string {
  const slot = formatNextSlot(iso, options);
  return slot ? `${slot.charAt(0).toUpperCase()}${slot.slice(1)}.` : "";
}

/** Why the toggle is off, in plain words; "" when emergencies are allowed. */
export function emergencyReasonText(
  eligibility: EmergencyEligibility,
  options: Options = {},
): string {
  const at = eligibility.next_allowed_at;
  switch (eligibility.reason) {
    case null:
      return "";
    case "unverified":
      return "Verify your email to post an emergency.";
    case "account_too_new":
      return at
        ? `Your account is too new for emergency posts. You can post one from ${formatDate(at)}.`
        : "Your account is too new for emergency posts.";
    case "score_too_low":
      return "Your credibility score is below the minimum for emergency posts.";
    case "blocked":
      return at
        ? `Emergency posting is blocked on your account until ${formatDate(at)}.`
        : "Emergency posting is blocked on your account.";
    case "daily_limit":
      return at
        ? `You've posted an emergency in the last 24 hours. ${nextSlot(at, options)}`.trim()
        : "Emergency posts are paused right now.";
    case "fact_quota":
      return at
        ? `You've used all your fact posts for the last 24 hours. ${nextSlot(at, options)}`.trim()
        : "Fact posts are paused right now.";
  }
}
