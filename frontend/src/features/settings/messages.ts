/** What Settings says (ARCHITECTURE §7, §9; Part 14). */
import { ApiError } from "@/lib/api/client";

export const SETTINGS_MESSAGES = {
  profileSaved: "Profile saved.",
  passwordChanged: "Password changed. Your other devices are signed out.",
  accountDeleted: "Your account has been deleted.",
  unverified: "Verify your email address to edit your profile.",
  exportFailed: "Couldn't prepare your data. Try again.",
  exportThrottled: "You've downloaded your data a few times already. Try again in an hour.",
  rateLimited: "Too many tries. Wait a little and try again.",
  waking: "The server is waking up. Try again in a minute.",
  network: "Can't reach Rumor Zero. Check your connection and try again.",
  generic: "Something went wrong. Try again.",
  staffAccount: "Staff accounts can't delete themselves. Ask an admin to remove your role first.",
  noPassword: "This account has no password. Use Forgot password to set one.",
  signedOut: "You were signed out. Log in again and retry.",
} as const;

/** The banner text for a failed settings request; field errors are shown on their fields. */
export function settingsErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return SETTINGS_MESSAGES.generic;
  if (error.status === 429) return SETTINGS_MESSAGES.rateLimited;
  if (error.status === 503) return SETTINGS_MESSAGES.waking;
  if (error.status === 0) return SETTINGS_MESSAGES.network;
  if (error.status === 401) return SETTINGS_MESSAGES.signedOut;
  if (error.code === "email_unverified") return SETTINGS_MESSAGES.unverified;
  if (error.code === "staff_account") return SETTINGS_MESSAGES.staffAccount;
  if (error.code === "password_not_set") return SETTINGS_MESSAGES.noPassword;
  return SETTINGS_MESSAGES.generic;
}
