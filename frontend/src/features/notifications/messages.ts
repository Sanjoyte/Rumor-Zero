/** What the notifications screen says (ARCHITECTURE §10). Errors map from `ApiError`. */
import { waitText } from "@/features/posts/messages";
import { ApiError } from "@/lib/api/client";
import type { NotificationData } from "@/lib/api/types";

export const NOTIFICATION_MESSAGES = {
  title: "Notifications",
  listFailed: "Couldn't load your notifications. Check your connection and try again.",
  waking: "The server is waking up. Try again in a minute.",
  moreFailed: "Couldn't load more notifications.",
  markAllFailed: "Couldn't mark your notifications as read. Try again.",
  emptyTitle: "Nothing yet",
  emptyBody:
    "When someone follows you, likes, comments on or reposts your posts, or a post of yours is checked or reviewed, you'll see it here.",
  endLabel: "You have reached the end of your notifications.",
  markAll: "Mark all as read",
  followBack: "Follow back",
  someone: "Someone",
} as const;

export function notificationsErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 503 || error.code === "backend_waking") {
      return NOTIFICATION_MESSAGES.waking;
    }
    if (error.status === 429) {
      return `You're going too fast. Try again ${waitText(error.retryAfter)}.`;
    }
  }
  return NOTIFICATION_MESSAGES.listFailed;
}

/** "3 unread", for the page chip and the badge's spoken name. */
export function unreadLabel(count: number): string {
  return `${count > 99 ? "99+" : count} unread`;
}

/** The badge text: the exact number up to 99. */
export function badgeText(count: number): string {
  return count > 99 ? "99+" : String(count);
}

/** Where a click on the item goes: the person for a follow, otherwise the post. */
export function notificationHref(item: NotificationData): string | null {
  if (item.type === "follow") return item.actor ? `/u/${item.actor.username}` : null;
  return item.post ? `/p/${item.post.id}` : null;
}

/** The person's name as written in the sentence ("Someone" for a system message or a gone account). */
export function actorName(item: NotificationData): string {
  const actor = item.actor;
  if (!actor) return NOTIFICATION_MESSAGES.someone;
  return actor.display_name.trim() || `@${actor.username}`;
}
