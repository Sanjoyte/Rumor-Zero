import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import { composerFailure, feedErrorMessage, POST_MESSAGES, waitText } from "./messages";

const api = (init: ConstructorParameters<typeof ApiError>[0]) => new ApiError(init);

describe("composerFailure", () => {
  it("reads the quota refusal by its code, not its 429", () => {
    const failure = composerFailure(
      api({
        status: 429,
        code: "fact_quota_exceeded",
        detail: "You've used all 10 of your fact posts for the last 24 hours.",
        retryAfter: 3600,
      }),
    );
    expect(failure.kind).toBe("quota");
    expect(failure.message).toContain("all 10 of your fact posts");
  });

  it("tells the throttle's 429 apart and says when to try again", () => {
    const failure = composerFailure(
      api({ status: 429, code: "throttled", detail: "Request was throttled.", retryAfter: 600 }),
    );
    expect(failure.kind).toBe("throttled");
    expect(failure.message).toBe("You're posting too fast. Try again in about 10 minutes.");
  });

  it.each([
    ["fact_posts_paused", 403, "paused", POST_MESSAGES.quotaPaused],
    ["email_unverified", 403, "unverified", POST_MESSAGES.verifyToPost],
    ["backend_waking", 503, "waking", POST_MESSAGES.waking],
    ["network_error", 0, "network", POST_MESSAGES.network],
  ] as const)("maps %s", (code, status, kind, message) => {
    const failure = composerFailure(api({ status, code, detail: "x" }));
    expect(failure.kind).toBe(kind);
    expect(failure.message).toBe(message);
  });

  it("puts field errors where they belong, by sent index", () => {
    const failure = composerFailure(
      api({
        status: 400,
        code: "invalid",
        detail: "Write something first.",
        fieldErrors: {
          content: ["Write something first."],
          post_type: ["Choose Opinion or Fact."],
          sources: ["You can add up to 5 sources."],
          "sources.1": ["Enter a link that starts with https://"],
          "sources.3": ["Same as source 1."],
        },
      }),
    );
    expect(failure.kind).toBe("fields");
    expect(failure.fields).toEqual({
      content: "Write something first.",
      postType: "Choose Opinion or Fact.",
      sources: "You can add up to 5 sources.",
      sourceRows: { 1: "Enter a link that starts with https://", 3: "Same as source 1." },
    });
    expect(failure.message).toBe("Fix the highlighted fields and try again.");
  });

  it("shows the server's own words for anything else", () => {
    expect(
      composerFailure(api({ status: 400, code: "emergency_unavailable", detail: "No." })),
    ).toMatchObject({
      kind: "other",
      message: "No.",
    });
  });

  it("copes with something that isn't an ApiError", () => {
    expect(composerFailure(new Error("boom"))).toMatchObject({
      kind: "other",
      message: POST_MESSAGES.generic,
    });
  });
});

describe("waitText", () => {
  it.each([
    [null, "in a minute"],
    [30, "in a minute"],
    [89, "in a minute"],
    [600, "in about 10 minutes"],
    [3600, "in about 60 minutes"],
    [6 * 3600, "in about 6 hours"],
  ])("%s seconds → %s", (seconds, text) => {
    expect(waitText(seconds)).toBe(text);
  });
});

describe("feedErrorMessage", () => {
  it("says the server is waking up on a 503, else a connection message", () => {
    expect(feedErrorMessage(api({ status: 503, code: "backend_waking", detail: "x" }))).toBe(
      POST_MESSAGES.feedWaking,
    );
    expect(feedErrorMessage(new Error("x"))).toBe(POST_MESSAGES.feedFailed);
  });
});
