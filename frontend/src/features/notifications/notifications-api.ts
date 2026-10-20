/**
 * The notification endpoints (ARCHITECTURE §9, Part 13). Ordinary app calls: they send the
 * in-memory access token and get the client's single refresh-and-retry on a 401.
 */
import { api } from "@/lib/api/client";
import type { CursorPage, NotificationData } from "@/lib/api/types";
import { withCursor } from "@/features/social/social-api";

export const NOTIFICATION_PATHS = {
  list: "/v1/notifications/",
  unreadCount: "/v1/notifications/unread-count/",
  markRead: "/v1/notifications/mark-read/",
} as const;

/** The most ids one mark-read call takes (the server refuses more). */
export const MAX_MARK_READ_IDS = 50;

export interface NotificationPage {
  items: NotificationData[];
  nextCursor: string | null;
}

/** One page of your notifications, newest first. */
export async function fetchNotifications(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<NotificationPage> {
  const body = await api.get<CursorPage<NotificationData>>(
    withCursor(NOTIFICATION_PATHS.list, cursor),
    { signal },
  );
  return { items: body.results, nextCursor: body.next_cursor };
}

/** How many notifications are unread: exact, one cheap query on the server. */
export async function fetchUnreadCount(signal?: AbortSignal): Promise<number> {
  const body = await api.get<{ count: number }>(NOTIFICATION_PATHS.unreadCount, { signal });
  return body.count;
}

/** Mark some of your notifications read, or all of them. Answers the unread count that is left. */
export async function markRead(target: { ids: string[] } | { all: true }): Promise<number> {
  const body = await api.post<{ count: number }>(NOTIFICATION_PATHS.markRead, target);
  return body.count;
}
