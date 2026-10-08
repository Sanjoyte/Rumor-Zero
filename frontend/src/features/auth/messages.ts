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
  // Part 2: verification and password reset
  resendSent: "We sent a new verification link. Check your inbox.",
  resendThrottled: "We sent one recently. Wait a little before asking again.",
  alreadyVerified: "Your email is already verified.",
  newPostBlocked:
    "Verify your email to post. Check your inbox, or resend the link from the banner.",
  passwordChanged: "Password changed. You're logged in.",
  passwordChangedLogIn: "Password changed. Log in with your new password.",
  resetUnreachable: "We couldn't check this link. Try again.",
  // Part 3: Continue with Google
  googleFailed: "Google sign-in didn't work. Try again.",
  googleUnverified:
    "Your Google account's email address isn't verified. Verify it with Google, or sign up with email.",
  accountInactive: "This account can't sign in.",
  staffPasswordLogin: "Staff accounts log in with their password.",
  googleLinkRequiresPassword:
    "An account with this email already exists. Log in with your password.",
  googleUnavailable: "Google sign-in couldn't load. Check your connection, or use email.",
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

const GOOGLE_CODES: Record<string, string> = {
  invalid_token: MESSAGES.googleFailed,
  google_email_unverified: MESSAGES.googleUnverified,
  account_inactive: MESSAGES.accountInactive,
  staff_password_login: MESSAGES.staffPasswordLogin,
  google_link_requires_password: MESSAGES.googleLinkRequiresPassword,
};

/** The banner text for a failed Google sign-in; rate limits, outages and the like fall through. */
export function googleErrorMessage(error: unknown): string {
  if (error instanceof ApiError && GOOGLE_CODES[error.code]) return GOOGLE_CODES[error.code];
  return bannerMessage(error);
}
