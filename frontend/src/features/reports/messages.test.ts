import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import { REPORT_MESSAGES, reportFailure } from "./messages";
import { isReportReason, REPORT_REASONS } from "./reasons";

const fail = (init: Partial<ConstructorParameters<typeof ApiError>[0]> & { status: number }) =>
  reportFailure(new ApiError({ code: "x", detail: "", ...init }));

describe("reportFailure", () => {
  it("ends the flow for an already-reported post and a gone one", () => {
    expect(fail({ status: 409, code: "already_reported" }).kind).toBe("already");
    expect(fail({ status: 404, code: "not_found" }).kind).toBe("gone");
  });

  it("maps the other server answers to one message each", () => {
    const cases: [Parameters<typeof fail>[0], string][] = [
      [{ status: 403, code: "email_unverified" }, REPORT_MESSAGES.verifyInModal],
      [{ status: 403, code: "cannot_report_own" }, REPORT_MESSAGES.own],
      [{ status: 401, code: "not_authenticated" }, REPORT_MESSAGES.signedOut],
      [{ status: 0, code: "network_error" }, REPORT_MESSAGES.network],
      [{ status: 503, code: "backend_waking" }, REPORT_MESSAGES.waking],
      [{ status: 500, code: "server_error" }, REPORT_MESSAGES.failed],
    ];
    for (const [init, message] of cases) {
      expect(fail(init)).toEqual({ kind: "other", message, fields: {} });
    }
  });

  it("says how long to wait when throttled, by code or by status", () => {
    const byCode = fail({ status: 429, code: "throttled", retryAfter: 3600 });
    expect(byCode.message).toBe("You're reporting too fast. Try again in about 60 minutes.");
    expect(fail({ status: 429, code: "weird", retryAfter: null }).message).toBe(
      "You're reporting too fast. Try again in a minute.",
    );
  });

  it("hands field errors back to the fields", () => {
    const result = fail({
      status: 400,
      code: "validation_error",
      fieldErrors: { reason: ["Choose a reason."], details: ["Tell us what's wrong."] },
    });
    expect(result).toEqual({
      kind: "fields",
      message: "",
      fields: { reason: "Choose a reason.", details: "Tell us what's wrong." },
    });
  });

  it("treats a 400 without field errors as a generic failure", () => {
    expect(fail({ status: 400, code: "validation_error" }).kind).toBe("other");
  });

  it("treats anything that isn't an ApiError as a generic failure", () => {
    expect(reportFailure(new Error("boom"))).toEqual({
      kind: "other",
      message: REPORT_MESSAGES.failed,
      fields: {},
    });
  });
});

describe("report reasons", () => {
  it("are the five of ANALYSIS b-5, in order", () => {
    expect(REPORT_REASONS.map((reason) => reason.value)).toEqual([
      "inaccurate",
      "misleading",
      "harassment",
      "spam",
      "other",
    ]);
  });

  it("know which values are reasons", () => {
    expect(isReportReason("spam")).toBe(true);
    expect(isReportReason("nonsense")).toBe(false);
    expect(isReportReason(null)).toBe(false);
  });
});
