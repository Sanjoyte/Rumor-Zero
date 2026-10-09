/** What the composer and the feed say (ANALYSIS b-2, b-5). Errors map from `ApiError`. */
import { ApiError } from "@/lib/api/client";

export const POST_MESSAGES = {
  posted: "Posted.",
  postedFact: "Posted. Checking the facts…",
  postFailedKept: "Couldn't post. Your text is saved, so you can try again.",
  verifyToPost: "Verify your email to post. Check your inbox for the link.",
  quotaPaused: "Fact posts are paused right now. You can still post opinions.",
  waking: "The server is waking up. If your post doesn't show up in Recent in a minute, try again.",
  network: "Can't reach Rumor Zero. Check your connection and try again.",
  generic: "Something went wrong. Try again.",
  feedFailed: "Couldn't load posts. Check your connection and try again.",
  feedWaking: "The server is waking up. Try again in a minute.",
  moreFailed: "Couldn't load more posts.",
} as const;

/** "in about 5 minutes", from a Retry-After in seconds. */
export function waitText(seconds: number | null): string {
  if (!seconds || seconds < 90) return "in a minute";
  const minutes = Math.ceil(seconds / 60);
  if (minutes < 90) return `in about ${minutes} minutes`;
  return `in about ${Math.ceil(minutes / 60)} hours`;
}

export type ComposerFailureKind =
  "fields" | "quota" | "paused" | "throttled" | "unverified" | "waking" | "network" | "other";

export interface ComposerFailure {
  kind: ComposerFailureKind;
  /** The banner text. Field errors also set `fields`; the banner then just points at them. */
  message: string;
  fields: {
    content?: string;
    postType?: string;
    /** The list rule ("You can add up to 5 sources."). */
    sources?: string;
    /** By index in the list that was sent (empty rows are dropped, so not the row number). */
    sourceRows: Record<number, string>;
  };
}

/** Turn what `POST /api/v1/posts/` threw into one thing the composer can show. */
export function composerFailure(error: unknown): ComposerFailure {
  const fields: ComposerFailure["fields"] = { sourceRows: {} };
  if (!(error instanceof ApiError))
    return { kind: "other", message: POST_MESSAGES.generic, fields };
  // The code first: every 429 would otherwise read as the generic rate limit.
  switch (error.code) {
    case "fact_quota_exceeded":
      return { kind: "quota", message: error.detail, fields };
    case "fact_posts_paused":
      return { kind: "paused", message: POST_MESSAGES.quotaPaused, fields };
    case "email_unverified":
      return { kind: "unverified", message: POST_MESSAGES.verifyToPost, fields };
    case "throttled":
      return {
        kind: "throttled",
        message: `You're posting too fast. Try again ${waitText(error.retryAfter)}.`,
        fields,
      };
    case "backend_waking":
      return { kind: "waking", message: POST_MESSAGES.waking, fields };
    case "network_error":
      return { kind: "network", message: POST_MESSAGES.network, fields };
  }
  const errors = error.fieldErrors;
  if (errors.content?.[0]) fields.content = errors.content[0];
  if (errors.post_type?.[0]) fields.postType = errors.post_type[0];
  if (errors.sources?.[0]) fields.sources = errors.sources[0];
  for (const [key, messages] of Object.entries(errors)) {
    const row = /^sources\.(\d+)$/.exec(key);
    if (row && messages[0]) fields.sourceRows[Number(row[1])] = messages[0];
  }
  const hasField =
    fields.content ||
    fields.postType ||
    fields.sources ||
    Object.keys(fields.sourceRows).length > 0;
  if (hasField) {
    return { kind: "fields", message: "Fix the highlighted fields and try again.", fields };
  }
  return { kind: "other", message: error.detail || POST_MESSAGES.generic, fields };
}

/** Why the first page of a feed failed. */
export function feedErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 503) return POST_MESSAGES.feedWaking;
  return POST_MESSAGES.feedFailed;
}
