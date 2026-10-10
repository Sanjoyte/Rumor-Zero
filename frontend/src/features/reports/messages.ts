/** What the report button and modal say (ANALYSIS b-5, d1). Errors map from `ApiError`. */
import { waitText } from "@/features/posts/messages";
import { ApiError } from "@/lib/api/client";

export const REPORT_MESSAGES = {
  chooseReason: "Choose a reason.",
  detailsRequired: "Tell us what's wrong.",
  detailsTooLong: "Keep it to 500 characters.",
  sent: "Report sent. Thank you.",
  already: "You already reported this post.",
  gone: "This post is no longer available.",
  own: "You can't report your own post.",
  verifyInModal: "Verify your email to report.",
  verifyHint: "Verify your email to report posts.",
  verifyToast: "Verify your email to report posts. Check your inbox for the link.",
  logIn: "Log in to report",
  signedOut: "You were signed out. Log in and try again.",
  network: "Can't reach Rumor Zero. Check your connection and try again.",
  waking: "The server is waking up. Try again in a minute.",
  failed: "Couldn't send your report. Your choices are still here. Try again.",
} as const;

export interface ReportFailure {
  /**
   * `already` and `gone` end the flow (the modal closes and the button follows the server);
   * `fields` and the rest keep the modal open with the choices in it.
   */
  kind: "already" | "gone" | "fields" | "other";
  /** The banner text; empty for `already`, `gone` and `fields`. */
  message: string;
  fields: { reason?: string; details?: string };
}

/** What a failed report means for the modal. */
export function reportFailure(error: unknown): ReportFailure {
  const other = (message: string): ReportFailure => ({ kind: "other", message, fields: {} });
  if (!(error instanceof ApiError)) return other(REPORT_MESSAGES.failed);
  if (error.code === "already_reported") return { kind: "already", message: "", fields: {} };
  if (error.status === 404) return { kind: "gone", message: "", fields: {} };
  if (error.code === "email_unverified") return other(REPORT_MESSAGES.verifyInModal);
  if (error.code === "cannot_report_own") return other(REPORT_MESSAGES.own);
  if (error.code === "throttled" || error.status === 429) {
    return other(`You're reporting too fast. Try again ${waitText(error.retryAfter)}.`);
  }
  if (error.status === 400) {
    const reason = error.fieldErrors?.reason?.[0];
    const details = error.fieldErrors?.details?.[0];
    if (reason || details) return { kind: "fields", message: "", fields: { reason, details } };
  }
  if (error.status === 401) return other(REPORT_MESSAGES.signedOut);
  if (error.code === "network_error") return other(REPORT_MESSAGES.network);
  if (error.code === "backend_waking") return other(REPORT_MESSAGES.waking);
  return other(REPORT_MESSAGES.failed);
}
