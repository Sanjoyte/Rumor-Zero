import { describe, expect, it } from "vitest";
import { SOCIAL_MESSAGES } from "./messages";
import { repostBlockedReason } from "./repost-rules";

describe("repostBlockedReason", () => {
  it("is null for someone else's post in any state the server accepts", () => {
    for (const status of ["pending", "published", "verified_true", "under_review"] as const) {
      expect(repostBlockedReason({ is_mine: false, status })).toBeNull();
    }
  });

  it("explains each refusal", () => {
    expect(repostBlockedReason({ is_mine: true, status: "published" })).toBe(
      SOCIAL_MESSAGES.cannotRepostOwn,
    );
    expect(repostBlockedReason({ is_mine: false, status: "verified_false" })).toBe(
      SOCIAL_MESSAGES.cannotRepostFalse,
    );
    expect(repostBlockedReason({ is_mine: false, status: "removed" })).toBe(
      SOCIAL_MESSAGES.cannotRepostRemoved,
    );
  });

  it("says 'your own' first, as the server checks it first", () => {
    expect(repostBlockedReason({ is_mine: true, status: "verified_false" })).toBe(
      SOCIAL_MESSAGES.cannotRepostOwn,
    );
    expect(repostBlockedReason({ is_mine: true, status: "removed" })).toBe(
      SOCIAL_MESSAGES.cannotRepostOwn,
    );
  });
});
