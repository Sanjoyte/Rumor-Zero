import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import { APPEAL_MESSAGES, appealFailure } from "./messages";

const fail = (init: Partial<ConstructorParameters<typeof ApiError>[0]> & { status: number }) =>
  appealFailure(new ApiError({ code: "x", detail: "", ...init }));

describe("appealFailure", () => {
  it("ends the flow for an appeal that exists, a post that can't be appealed and a gone post", () => {
    expect(fail({ status: 409, code: "already_appealed" })).toEqual({
      kind: "already",
      message: "",
      fields: {},
    });
    expect(fail({ status: 409, code: "not_appealable" }).kind).toBe("not_appealable");
    expect(fail({ status: 404, code: "not_found" }).kind).toBe("gone");
  });

  it("maps the other server answers to one message each", () => {
    const cases: [Parameters<typeof fail>[0], string][] = [
      [{ status: 403, code: "email_unverified" }, APPEAL_MESSAGES.verifyInModal],
      [{ status: 403, code: "not_author" }, APPEAL_MESSAGES.notAuthor],
      [{ status: 401, code: "not_authenticated" }, APPEAL_MESSAGES.signedOut],
      [{ status: 0, code: "network_error" }, APPEAL_MESSAGES.network],
      [{ status: 503, code: "backend_waking" }, APPEAL_MESSAGES.waking],
      [{ status: 500, code: "server_error" }, APPEAL_MESSAGES.failed],
    ];
    for (const [init, message] of cases) {
      expect(fail(init)).toEqual({ kind: "other", message, fields: {} });
    }
  });

  it("says how long to wait when throttled, by code or by status", () => {
    const byCode = fail({ status: 429, code: "throttled", retryAfter: 5 * 3600 });
    expect(byCode.message).toBe(
      "You've asked for another look too often today. Try again in about 5 hours.",
    );
    expect(fail({ status: 429, code: "weird", retryAfter: null }).message).toBe(
      "You've asked for another look too often today. Try again in a minute.",
    );
  });

  it("hands a reason error back to the field", () => {
    expect(
      fail({
        status: 400,
        code: "validation_error",
        fieldErrors: { reason: ["Keep it to 500 characters."] },
      }),
    ).toEqual({ kind: "fields", message: "", fields: { reason: "Keep it to 500 characters." } });
  });

  it("falls back to the general message for a 400 with nothing for the field", () => {
    expect(fail({ status: 400, code: "bad" }).message).toBe(APPEAL_MESSAGES.failed);
  });

  it("falls back to the general message for anything that isn't an ApiError", () => {
    expect(appealFailure(new Error("boom"))).toEqual({
      kind: "other",
      message: APPEAL_MESSAGES.failed,
      fields: {},
    });
  });

  it("never uses the word 'debunked' or admin jargon", () => {
    const text = JSON.stringify(APPEAL_MESSAGES);
    expect(text).not.toMatch(/debunk|adjudicat|protocol/i);
  });
});
