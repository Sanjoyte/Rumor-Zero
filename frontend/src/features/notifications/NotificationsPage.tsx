"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useCursorFeed } from "@/features/posts/useCursorFeed";
import type { NotificationData } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { NOTIFICATION_MESSAGES, unreadLabel } from "./messages";
import { fetchNotifications, markRead } from "./notifications-api";
import { NotificationList, notificationKey } from "./NotificationList";
import { useUnreadCount } from "./UnreadCountProvider";

const CONTAINER =
  "mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg";

const EMPTY: ReadonlySet<string> = new Set();

/**
 * `/notifications` (Stitch c4): the title with an "N unread" chip, Mark all as read, and the items
 * newest first. Marking read is optimistic and rolls back with a toast. Opening an item marks it
 * read at once and in the background. While the page is open, a poll that finds more unread items
 * than before fetches the first page again and puts the new ones on top; nothing else resets, so
 * the loaded pages and the scroll position stay.
 */
export function NotificationsPage({ now }: { now?: Date }) {
  const { status, user } = useAuth();
  const toast = useToast();
  const unread = useUnreadCount();
  const feed = useCursorFeed({
    fetchPage: fetchNotifications,
    keyOf: notificationKey,
    // A first request before the session is known would go out without the token.
    enabled: status === "authenticated",
    resetKey: user?.id ?? null,
  });
  const [readIds, setReadIds] = useState<ReadonlySet<string>>(EMPTY);
  const [busy, setBusy] = useState(false);
  const marking = useRef(false);

  const { prepend } = feed;
  const seenArrivals = useRef(unread.arrivals);
  useEffect(() => {
    if (unread.arrivals === seenArrivals.current) return;
    seenArrivals.current = unread.arrivals;
    const controller = new AbortController();
    fetchNotifications(null, controller.signal).then(
      (page) => {
        if (controller.signal.aborted) return;
        // Oldest first, so the newest ends up on top. Items already on screen are prepended too:
        // the list drops the older copy, so they come back fresh (read elsewhere, say).
        for (const item of [...page.items].reverse()) prepend(item);
      },
      () => {
        // Silent: the next poll that sees a rise tries again.
      },
    );
    return () => controller.abort();
  }, [unread.arrivals, prepend]);

  const { adjust, set } = unread;
  const onOpen = useCallback(
    (item: NotificationData) => {
      if (item.is_read || readIds.has(item.id)) return;
      setReadIds((prev) => new Set(prev).add(item.id));
      adjust(-1);
      // In the background: the page is about to change. The answer is the authoritative count.
      markRead({ ids: [item.id] }).then(set, () => {});
    },
    [readIds, adjust, set],
  );

  async function markAll() {
    if (marking.current) return;
    marking.current = true;
    setBusy(true);
    const before = { count: unread.count, readIds };
    setReadIds((prev) => new Set([...prev, ...feed.items.map(notificationKey)]));
    set(0);
    try {
      set(await markRead({ all: true }));
    } catch {
      setReadIds(before.readIds);
      set(before.count);
      toast.show(NOTIFICATION_MESSAGES.markAllFailed, { tone: "error" });
    } finally {
      marking.current = false;
      setBusy(false);
    }
  }

  return (
    <div className={CONTAINER}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-space-md gap-y-space-xs">
        <div className="flex items-center gap-space-md">
          <h1 className="font-headline-lg text-headline-lg tracking-tight text-on-surface">
            {NOTIFICATION_MESSAGES.title}
          </h1>
          {unread.count > 0 && (
            <span className="inline-flex items-center rounded-lg border border-outline-variant/30 bg-surface-container px-space-sm py-0.5 font-label-code text-label-code whitespace-nowrap text-on-surface-variant">
              {unreadLabel(unread.count)}
            </span>
          )}
        </div>
        {unread.count > 0 && (
          <button
            type="button"
            onClick={() => void markAll()}
            disabled={busy}
            className="shrink-0 font-body-sm text-body-sm font-medium text-secondary transition-colors hover:underline focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none disabled:opacity-60"
          >
            {NOTIFICATION_MESSAGES.markAll}
          </button>
        )}
      </div>
      <NotificationList feed={feed} readIds={readIds} onOpen={onOpen} now={now} />
    </div>
  );
}
