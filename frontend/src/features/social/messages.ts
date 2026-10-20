/** What the profile, follow and list screens say (ARCHITECTURE §10). Errors map from `ApiError`. */
import { ApiError } from "@/lib/api/client";
import { waitText } from "@/features/posts/messages";

export const SOCIAL_MESSAGES = {
  verifyToFollow: "Verify your email to follow people. Check your inbox for the link.",
  followFailed: "Couldn't follow. Try again.",
  unfollowFailed: "Couldn't unfollow. Try again.",
  gone: "That account is gone.",
  signedOut: "You were signed out. Log in and try again.",
  network: "Can't reach Rumor Zero. Check your connection and try again.",
  waking: "The server is waking up. Try again in a minute.",
  profileFailed: "Couldn't load this profile. Check your connection and try again.",
  profileNotFound: "There is no account with that username.",
  listFailed: "Couldn't load this list. Check your connection and try again.",
  moreFailed: "Couldn't load more people.",
  verifyToLike: "Verify your email to like posts. Check your inbox for the link.",
  likeFailed: "Couldn't like that post. Try again.",
  unlikeFailed: "Couldn't remove your like. Try again.",
  postGone: "That post is gone.",
  verifyToComment: "Verify your email to comment.",
  logInToComment: "Log in to comment",
  commentBlank: "Write something first.",
  commentTooLong: "Keep it to 500 characters.",
  commentFailed: "Couldn't post your comment. Your text is still here. Try again.",
  commentDeleted: "Comment deleted.",
  commentDeleteFailed: "Couldn't delete the comment. Check your connection and try again.",
  commentsFailed: "Couldn't load the comments. Check your connection and try again.",
  moreCommentsFailed: "Couldn't load more comments.",
  verifyToRepost: "Verify your email to repost posts. Check your inbox for the link.",
  repostFailed: "Couldn't repost that post. Try again.",
  unrepostFailed: "Couldn't undo your repost. Try again.",
  repostUndone: "Repost removed.",
  cannotRepostOwn: "You can't repost your own post.",
  cannotRepostFalse: "Posts labelled FALSE can't be reposted.",
  cannotRepostRemoved: "Removed posts can't be reposted.",
  bookmarkFailed: "Couldn't bookmark that post. Try again.",
  unbookmarkFailed: "Couldn't remove your bookmark. Try again.",
} as const;

/** The toast after a follow or unfollow that was rolled back. */
export function followFailureMessage(error: unknown, wasFollowing: boolean): string {
  if (error instanceof ApiError) {
    if (error.code === "email_unverified") return SOCIAL_MESSAGES.verifyToFollow;
    if (error.code === "throttled" || error.status === 429) {
      return `You're following people too fast. Try again ${waitText(error.retryAfter)}.`;
    }
    if (error.status === 404) return SOCIAL_MESSAGES.gone;
    if (error.status === 401) return SOCIAL_MESSAGES.signedOut;
    if (error.code === "network_error") return SOCIAL_MESSAGES.network;
    if (error.code === "backend_waking") return SOCIAL_MESSAGES.waking;
  }
  return wasFollowing ? SOCIAL_MESSAGES.unfollowFailed : SOCIAL_MESSAGES.followFailed;
}

export function listErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 503) return SOCIAL_MESSAGES.waking;
  // People search is limited per address (Part 12); no other list answers 429.
  if (error instanceof ApiError && error.status === 429) {
    return `You're going too fast. Try again ${waitText(error.retryAfter)}.`;
  }
  return SOCIAL_MESSAGES.listFailed;
}

/** The toast after a like or unlike that was rolled back. */
export function likeFailureMessage(error: unknown, wasLiked: boolean): string {
  if (error instanceof ApiError) {
    if (error.code === "email_unverified") return SOCIAL_MESSAGES.verifyToLike;
    if (error.code === "throttled" || error.status === 429) {
      return `You're liking posts too fast. Try again ${waitText(error.retryAfter)}.`;
    }
    if (error.status === 404) return SOCIAL_MESSAGES.postGone;
    if (error.status === 401) return SOCIAL_MESSAGES.signedOut;
    if (error.code === "network_error") return SOCIAL_MESSAGES.network;
    if (error.code === "backend_waking") return SOCIAL_MESSAGES.waking;
  }
  return wasLiked ? SOCIAL_MESSAGES.unlikeFailed : SOCIAL_MESSAGES.likeFailed;
}

/** The toast after a repost or undo that was rolled back. */
export function repostFailureMessage(error: unknown, wasReposted: boolean): string {
  if (error instanceof ApiError) {
    if (error.code === "cannot_repost_own") return SOCIAL_MESSAGES.cannotRepostOwn;
    if (error.code === "cannot_repost_false") return SOCIAL_MESSAGES.cannotRepostFalse;
    if (error.code === "email_unverified") return SOCIAL_MESSAGES.verifyToRepost;
    if (error.code === "throttled" || error.status === 429) {
      return `You're reposting too fast. Try again ${waitText(error.retryAfter)}.`;
    }
    if (error.status === 404) return SOCIAL_MESSAGES.postGone;
    if (error.status === 401) return SOCIAL_MESSAGES.signedOut;
    if (error.code === "network_error") return SOCIAL_MESSAGES.network;
    if (error.code === "backend_waking") return SOCIAL_MESSAGES.waking;
  }
  return wasReposted ? SOCIAL_MESSAGES.unrepostFailed : SOCIAL_MESSAGES.repostFailed;
}

/** The toast after a bookmark or its removal that was rolled back. */
export function bookmarkFailureMessage(error: unknown, wasBookmarked: boolean): string {
  if (error instanceof ApiError) {
    if (error.code === "throttled" || error.status === 429) {
      return `You're bookmarking too fast. Try again ${waitText(error.retryAfter)}.`;
    }
    if (error.status === 404) return SOCIAL_MESSAGES.postGone;
    if (error.status === 401) return SOCIAL_MESSAGES.signedOut;
    if (error.code === "network_error") return SOCIAL_MESSAGES.network;
    if (error.code === "backend_waking") return SOCIAL_MESSAGES.waking;
  }
  return wasBookmarked ? SOCIAL_MESSAGES.unbookmarkFailed : SOCIAL_MESSAGES.bookmarkFailed;
}

/** The text shown above a comment composer after a failed send. The draft is kept. */
export function commentFailureMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "email_unverified") return SOCIAL_MESSAGES.verifyToComment;
    if (error.code === "throttled" || error.status === 429) {
      return `You're commenting too fast. Try again ${waitText(error.retryAfter)}.`;
    }
    const field = error.fieldErrors?.content?.[0];
    if (error.status === 400 && field) return field;
    if (error.status === 404) return SOCIAL_MESSAGES.postGone;
    if (error.status === 401) return SOCIAL_MESSAGES.signedOut;
    if (error.code === "network_error") return SOCIAL_MESSAGES.network;
    if (error.code === "backend_waking") return SOCIAL_MESSAGES.waking;
  }
  return SOCIAL_MESSAGES.commentFailed;
}

export function commentsErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 503) return SOCIAL_MESSAGES.waking;
  return SOCIAL_MESSAGES.commentsFailed;
}
