/** What the auth forms say when a request fails (ARCHITECTURE §7; ANALYSIS b-2). */
import { ApiError } from "@/lib/api/client";

export const MESSAGES = {
  mismatch: "That email and password don't match.",
  rateLimited: "Too many attempts. Try again in a few minutes.",
  waking: "The server is waking up. Try again in a minute.",
  reload: "Something went wrong. Reload the page and try again.",
  network: "Can't reach Rumor Zero. Check your connection and try again.",
  generic: "Something went wrong. Try again.",
  turnstileUnavailable: "We couldn't run the bot check. Try again in a minute.",
} as const;

/** The banner text for errors that don't belong to one field. */
export function bannerMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return MESSAGES.generic;
  if (error.code === "email_password_mismatch") return MESSAGES.mismatch;
  if (error.code === "too_many_login_attempts" || error.status === 429) {
    return MESSAGES.rateLimited;
  }
  if (error.status === 503) return MESSAGES.waking;
  if (error.code === "csrf_failed") return MESSAGES.reload;
  if (error.status === 0) return MESSAGES.network;
  return MESSAGES.generic;
}
