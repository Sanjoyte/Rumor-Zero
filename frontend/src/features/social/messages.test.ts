import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import {
  bookmarkFailureMessage,
  commentFailureMessage,
  commentsErrorMessage,
  followFailureMessage,
  likeFailureMessage,
  listErrorMessage,
  repostFailureMessage,
  SOCIAL_MESSAGES,
} from "./messages";

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

  it("says a 429 is the rate limit and when to try again (people search, Part 12)", () => {
    expect(listErrorMessage(err(429, "throttled", 20))).toBe(
      "You're going too fast. Try again in a minute.",
    );
    expect(listErrorMessage(err(429, "throttled", 3600))).toBe(
      "You're going too fast. Try again in about 60 minutes.",
    );
  });
});

describe("likeFailureMessage", () => {
  it("maps each known failure", () => {
    expect(likeFailureMessage(err(403, "email_unverified"), false)).toBe(
      SOCIAL_MESSAGES.verifyToLike,
    );
    expect(likeFailureMessage(err(404, "not_found"), false)).toBe(SOCIAL_MESSAGES.postGone);
    expect(likeFailureMessage(err(401, "not_authenticated"), true)).toBe(SOCIAL_MESSAGES.signedOut);
    expect(likeFailureMessage(err(0, "network_error"), true)).toBe(SOCIAL_MESSAGES.network);
    expect(likeFailureMessage(err(503, "backend_waking"), true)).toBe(SOCIAL_MESSAGES.waking);
  });

  it("says how long to wait when throttled", () => {
    expect(likeFailureMessage(err(429, "throttled", 1800), false)).toContain("about 30 minutes");
  });

  it("falls back to a message for the direction", () => {
    expect(likeFailureMessage(err(500, "server_error"), false)).toBe(SOCIAL_MESSAGES.likeFailed);
    expect(likeFailureMessage(new Error("boom"), true)).toBe(SOCIAL_MESSAGES.unlikeFailed);
  });
});

describe("commentFailureMessage", () => {
  it("shows the server's own words for a bad text", () => {
    const error = new ApiError({
      status: 400,
      code: "invalid",
      detail: "x",
      fieldErrors: { content: ["Keep it to 500 characters."] },
    });
    expect(commentFailureMessage(error)).toBe("Keep it to 500 characters.");
  });

  it("maps the other failures", () => {
    expect(commentFailureMessage(err(403, "email_unverified"))).toBe(
      SOCIAL_MESSAGES.verifyToComment,
    );
    expect(commentFailureMessage(err(404, "not_found"))).toBe(SOCIAL_MESSAGES.postGone);
    expect(commentFailureMessage(err(401, "not_authenticated"))).toBe(SOCIAL_MESSAGES.signedOut);
    expect(commentFailureMessage(err(0, "network_error"))).toBe(SOCIAL_MESSAGES.network);
    expect(commentFailureMessage(err(429, "throttled", 600))).toContain("about 10 minutes");
    expect(commentFailureMessage(err(500, "server_error"))).toBe(SOCIAL_MESSAGES.commentFailed);
    expect(commentFailureMessage(new Error("boom"))).toBe(SOCIAL_MESSAGES.commentFailed);
  });
});

describe("commentsErrorMessage", () => {
  it("says the server is waking up on a 503, else the generic text", () => {
    expect(commentsErrorMessage(err(503, "backend_waking"))).toBe(SOCIAL_MESSAGES.waking);
    expect(commentsErrorMessage(err(500, "server_error"))).toBe(SOCIAL_MESSAGES.commentsFailed);
  });
});

describe("repostFailureMessage", () => {
  it("maps each known failure", () => {
    expect(repostFailureMessage(err(409, "cannot_repost_own"), false)).toBe(
      SOCIAL_MESSAGES.cannotRepostOwn,
    );
    expect(repostFailureMessage(err(409, "cannot_repost_false"), false)).toBe(
      SOCIAL_MESSAGES.cannotRepostFalse,
    );
    expect(repostFailureMessage(err(403, "email_unverified"), false)).toBe(
      SOCIAL_MESSAGES.verifyToRepost,
    );
    expect(repostFailureMessage(err(404, "not_found"), false)).toBe(SOCIAL_MESSAGES.postGone);
    expect(repostFailureMessage(err(401, "not_authenticated"), true)).toBe(
      SOCIAL_MESSAGES.signedOut,
    );
    expect(repostFailureMessage(err(0, "network_error"), true)).toBe(SOCIAL_MESSAGES.network);
    expect(repostFailureMessage(err(503, "backend_waking"), true)).toBe(SOCIAL_MESSAGES.waking);
  });

  it("says how long to wait when throttled", () => {
    expect(repostFailureMessage(err(429, "throttled", 1800), false)).toContain("about 30 minutes");
  });

  it("falls back to a message for the direction", () => {
    expect(repostFailureMessage(err(500, "server_error"), false)).toBe(
      SOCIAL_MESSAGES.repostFailed,
    );
    expect(repostFailureMessage(new Error("boom"), true)).toBe(SOCIAL_MESSAGES.unrepostFailed);
  });
});

describe("bookmarkFailureMessage", () => {
  it("maps each known failure", () => {
    expect(bookmarkFailureMessage(err(404, "not_found"), false)).toBe(SOCIAL_MESSAGES.postGone);
    expect(bookmarkFailureMessage(err(401, "not_authenticated"), true)).toBe(
      SOCIAL_MESSAGES.signedOut,
    );
    expect(bookmarkFailureMessage(err(0, "network_error"), true)).toBe(SOCIAL_MESSAGES.network);
    expect(bookmarkFailureMessage(err(503, "backend_waking"), true)).toBe(SOCIAL_MESSAGES.waking);
    expect(bookmarkFailureMessage(err(429, "throttled", 1800), false)).toContain(
      "about 30 minutes",
    );
  });

  it("has no verified-email message: bookmarks are private", () => {
    expect(bookmarkFailureMessage(err(403, "email_unverified"), false)).toBe(
      SOCIAL_MESSAGES.bookmarkFailed,
    );
  });

  it("falls back to a message for the direction", () => {
    expect(bookmarkFailureMessage(err(500, "x"), false)).toBe(SOCIAL_MESSAGES.bookmarkFailed);
    expect(bookmarkFailureMessage(new Error("boom"), true)).toBe(SOCIAL_MESSAGES.unbookmarkFailed);
  });
});
