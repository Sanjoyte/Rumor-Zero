import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import { followFailureMessage, listErrorMessage, SOCIAL_MESSAGES } from "./messages";

const err = (status: number, code: string, retryAfter: number | null = null) =>
  new ApiError({ status, code, detail: "x", retryAfter });

describe("followFailureMessage", () => {
  it("maps each known failure", () => {
    expect(followFailureMessage(err(403, "email_unverified"), false)).toBe(
      SOCIAL_MESSAGES.verifyToFollow,
    );
    expect(followFailureMessage(err(404, "not_found"), false)).toBe(SOCIAL_MESSAGES.gone);
    expect(followFailureMessage(err(401, "not_authenticated"), true)).toBe(
      SOCIAL_MESSAGES.signedOut,
    );
    expect(followFailureMessage(err(0, "network_error"), true)).toBe(SOCIAL_MESSAGES.network);
    expect(followFailureMessage(err(503, "backend_waking"), true)).toBe(SOCIAL_MESSAGES.waking);
  });

  it("says how long to wait when throttled", () => {
    expect(followFailureMessage(err(429, "throttled", 1800), false)).toContain("about 30 minutes");
    expect(followFailureMessage(err(429, "throttled"), false)).toContain("in a minute");
  });

  it("falls back to a message for the direction", () => {
    expect(followFailureMessage(err(500, "server_error"), false)).toBe(
      SOCIAL_MESSAGES.followFailed,
    );
    expect(followFailureMessage(new Error("boom"), true)).toBe(SOCIAL_MESSAGES.unfollowFailed);
  });
});

describe("listErrorMessage", () => {
  it("tells a waking server from a failure", () => {
    expect(listErrorMessage(err(503, "backend_waking"))).toBe(SOCIAL_MESSAGES.waking);
    expect(listErrorMessage(new Error("x"))).toBe(SOCIAL_MESSAGES.listFailed);
  });
});
