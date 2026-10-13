/** What the appeal button and modal say (ANALYSIS b-2, f-2). Errors map from `ApiError`. */
import { waitText } from "@/features/posts/messages";
import { ApiError } from "@/lib/api/client";

export const APPEAL_MESSAGES = {
  reasonTooLong: "Keep it to 500 characters.",
  sent: "Request sent. A moderator will take another look.",
  already: "You already asked for another look at this post.",
  notAppealable: "Only posts labelled FALSE or removed can be appealed.",
  gone: "This post is no longer available.",
  notAuthor: "Only the author can ask for another look.",
  verifyInModal: "Verify your email to ask for another look.",
  verifyHint: "Verify your email to ask for another look.",
  verifyToast: "Verify your email to ask for another look. Check your inbox for the link.",
  signedOut: "You were signed out. Log in and try again.",
  network: "Can't reach Rumor Zero. Check your connection and try again.",
  waking: "The server is waking up. Try again in a minute.",
  failed: "Couldn't send your request. What you wrote is still here. Try again.",
} as const;

export interface AppealFailure {
  /**
   * `already`, `not_appealable` and `gone` end the flow (the modal closes and the page follows the
   * server); `fields` and the rest keep the modal open with the text in it.
   */
  kind: "already" | "not_appealable" | "gone" | "fields" | "other";
  /** The banner text; empty for the first four kinds. */
  message: string;
  fields: { reason?: string };
}

/** What a failed appeal means for the modal. */
export function appealFailure(error: unknown): AppealFailure {
  const other = (message: string): AppealFailure => ({ kind: "other", message, fields: {} });
  const ends = (kind: "already" | "not_appealable" | "gone"): AppealFailure => ({
    kind,
    message: "",
    fields: {},
  });
  if (!(error instanceof ApiError)) return other(APPEAL_MESSAGES.failed);
  if (error.code === "already_appealed") return ends("already");
  if (error.code === "not_appealable") return ends("not_appealable");
  if (error.status === 404) return ends("gone");
  if (error.code === "email_unverified") return other(APPEAL_MESSAGES.verifyInModal);
  if (error.code === "not_author") return other(APPEAL_MESSAGES.notAuthor);
  if (error.code === "throttled" || error.status === 429) {
    return other(
      `You've asked for another look too often today. Try again ${waitText(error.retryAfter)}.`,
    );
  }
  if (error.status === 400) {
    const reason = error.fieldErrors?.reason?.[0];
    if (reason) return { kind: "fields", message: "", fields: { reason } };
  }
  if (error.status === 401) return other(APPEAL_MESSAGES.signedOut);
  if (error.code === "network_error") return other(APPEAL_MESSAGES.network);
  if (error.code === "backend_waking") return other(APPEAL_MESSAGES.waking);
  return other(APPEAL_MESSAGES.failed);
}
