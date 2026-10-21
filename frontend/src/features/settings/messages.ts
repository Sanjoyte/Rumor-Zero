/** What Settings says (ARCHITECTURE §7, §9; Part 14). */
import { waitText } from "@/features/posts/messages";
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

/** What the photo card says (ARCHITECTURE §4e; Part 14B). */
export const PHOTO_MESSAGES = {
  title: "Profile photo",
  intro:
    "JPEG, PNG or WebP, at least 128 \u00d7 128 pixels. We crop it to a square and remove location and camera data.",
  saved: "Photo saved.",
  removed: "Photo removed.",
  blocked: "A moderator turned off photo uploads for your account.",
  unverified: "Verify your email address to add a photo.",
  // The browser's own checks, before anything is sent.
  type: "Choose a JPEG, PNG or WebP photo.",
  tooBig: "That file is over 20 MB. Choose a smaller one.",
  unreadable: "We can't read that file. Choose a JPEG, PNG or WebP photo.",
  tooSmall: "That photo is too small. Use one at least 128 \u00d7 128 pixels.",
  // The server's refusals.
  serverTooLarge: "That photo is still over 5 MB. Choose a smaller one.",
  serverUnsupported:
    "We can't use that file. Choose a JPEG, PNG or WebP photo that isn't animated.",
  tooManyPixels: "That photo has too many pixels. Choose a smaller one.",
  busy: "Photo uploads are busy right now. Try again in a few seconds.",
  cancelled: "Upload cancelled.",
} as const;

/** The text for a photo that can't be used or a request that failed. */
export function photoErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return SETTINGS_MESSAGES.generic;
  switch (error.code) {
    case "photo_uploads_blocked":
      return PHOTO_MESSAGES.blocked;
    case "email_unverified":
      return PHOTO_MESSAGES.unverified;
    case "photo_too_large":
    case "payload_too_large":
      return PHOTO_MESSAGES.serverTooLarge;
    case "photo_unsupported":
    case "photo_missing":
      return PHOTO_MESSAGES.serverUnsupported;
    case "photo_too_small":
      return PHOTO_MESSAGES.tooSmall;
    case "photo_too_many_pixels":
      return PHOTO_MESSAGES.tooManyPixels;
    case "photo_busy":
      return PHOTO_MESSAGES.busy;
  }
  if (error.status === 429) {
    return `You've changed your photo a few times today. Try again ${waitText(error.retryAfter)}.`;
  }
  if (error.status === 413) return PHOTO_MESSAGES.serverTooLarge;
  if (error.status === 503) return SETTINGS_MESSAGES.waking;
  if (error.status === 0) return SETTINGS_MESSAGES.network;
  if (error.status === 401) return SETTINGS_MESSAGES.signedOut;
  return SETTINGS_MESSAGES.generic;
}
