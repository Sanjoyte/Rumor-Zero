import { describe, expect, it } from "vitest";
import type { EmergencyEligibility, EmergencyReason } from "@/lib/api/types";
import { confirmationText, EMERGENCY_COPY, emergencyReasonText } from "./emergency-copy";

const NOW = new Date("2026-10-19T12:00:00Z");

function eligibility(
  reason: EmergencyReason | null,
  next_allowed_at: string | null = null,
): EmergencyEligibility {
  return { allowed: reason === null, reason, next_allowed_at, block_days: 30 };
}

const text = (reason: EmergencyReason | null, at: string | null = null) =>
  emergencyReasonText(eligibility(reason, at), { now: NOW, timeZone: "UTC" });

describe("emergencyReasonText", () => {
  it("says nothing when emergencies are allowed", () => {
    expect(text(null)).toBe("");
  });

  it("words every reason, with its time where there is one", () => {
    expect(text("unverified")).toBe("Verify your email to post an emergency.");
    expect(text("account_too_new", "2026-10-24T08:00:00Z")).toBe(
      "Your account is too new for emergency posts. You can post one from Oct 24, 2026.",
    );
    expect(text("score_too_low")).toBe(
      "Your credibility score is below the minimum for emergency posts.",
    );
    expect(text("blocked", "2026-11-18T12:00:00Z")).toBe(
      "Emergency posting is blocked on your account until Nov 18, 2026.",
    );
    expect(text("daily_limit", "2026-10-19T15:05:00Z")).toBe(
      "You've posted an emergency in the last 24 hours. Next at 3:05 PM.",
    );
    expect(text("daily_limit", "2026-10-20T02:10:00Z")).toBe(
      "You've posted an emergency in the last 24 hours. Next tomorrow at 2:10 AM.",
    );
    expect(text("fact_quota", "2026-10-19T15:05:00Z")).toBe(
      "You've used all your fact posts for the last 24 hours. Next at 3:05 PM.",
    );
  });

  it("says a paused setting is paused (no time to wait for)", () => {
    expect(text("daily_limit")).toBe("Emergency posts are paused right now.");
    expect(text("fact_quota")).toBe("Fact posts are paused right now.");
  });

  it("still words a time-bound reason sent without a time", () => {
    expect(text("account_too_new")).toBe("Your account is too new for emergency posts.");
    expect(text("blocked")).toBe("Emergency posting is blocked on your account.");
  });

  it("never says bypass, debunked or permanent", () => {
    const all = [
      ...Object.values(EMERGENCY_COPY),
      confirmationText(30),
      ...(
        [
          "unverified",
          "account_too_new",
          "score_too_low",
          "blocked",
          "daily_limit",
          "fact_quota",
        ] as const
      ).map((reason) => text(reason, "2026-10-20T10:00:00Z")),
    ].join(" ");
    expect(all).not.toMatch(/bypass|debunk|permanent/i);
  });
});

describe("confirmationText", () => {
  it("states the real block length", () => {
    expect(confirmationText(30)).toBe(
      "I understand emergency posts are checked first, and misuse lowers my credibility score and blocks emergency posting for 30 days.",
    );
    expect(confirmationText(1)).toMatch(/for 1 day\.$/);
  });

  it("drops the block clause when there is no block", () => {
    expect(confirmationText(0)).toBe(
      "I understand emergency posts are checked first, and misuse lowers my credibility score.",
    );
  });
});
