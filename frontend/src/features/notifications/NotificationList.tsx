"use client";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadMore } from "@/components/ui/LoadMore";
import { Skeleton } from "@/components/ui/Skeleton";
import type { CursorFeed } from "@/features/posts/useCursorFeed";
import type { NotificationData } from "@/lib/api/types";
import { NOTIFICATION_MESSAGES, notificationsErrorMessage } from "./messages";
import { NotificationItem } from "./NotificationItem";

export const notificationKey = (item: NotificationData) => item.id;

function RowSkeleton() {
  return (
    <div className="flex items-start gap-space-md px-space-md py-space-lg">
      <Skeleton className="h-9 w-9 shrink-0 rounded-lg" />
      <div className="flex flex-1 flex-col gap-space-xs">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
      <Skeleton className="h-3 w-8" />
    </div>
  );
}

export interface NotificationListProps {
  feed: CursorFeed<NotificationData>;
  /** Ids marked read on this page since they loaded (the server's copy catches up on a reload). */
  readIds: ReadonlySet<string>;
  onOpen: (item: NotificationData) => void;
  now?: Date;
}

/** The states of the list: skeleton, error with a retry, empty, and the items with Load more. */
export function NotificationList({ feed, readIds, onOpen, now }: NotificationListProps) {
  if (feed.phase === "idle" || feed.phase === "loading") {
    return (
      <div
        aria-busy="true"
        className="divide-y divide-outline-variant/30 rounded-lg border border-outline-variant/30 bg-surface-container-lowest"
      >
        <span className="sr-only">Loading notifications…</span>
        <RowSkeleton />
        <RowSkeleton />
        <RowSkeleton />
      </div>
    );
  }
  if (feed.phase === "error") {
    return (
      <Alert tone="error" title="Couldn't load your notifications">
        <p>{notificationsErrorMessage(feed.error)}</p>
        <Button variant="secondary" onClick={feed.retry} className="mt-space-md">
          Try again
        </Button>
      </Alert>
    );
  }
  if (feed.items.length === 0) {
    return (
      <EmptyState icon="notifications" title={NOTIFICATION_MESSAGES.emptyTitle}>
        {NOTIFICATION_MESSAGES.emptyBody}
      </EmptyState>
    );
  }
  return (
    <>
      <div className="divide-y divide-outline-variant/30 overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-lowest">
        {feed.items.map((item) => (
          <NotificationItem
            key={item.id}
            item={item}
            read={item.is_read || readIds.has(item.id)}
            onOpen={onOpen}
            now={now}
          />
        ))}
      </div>
      {feed.moreError !== null && (
        <Alert tone="error" className="mt-space-md">
          {NOTIFICATION_MESSAGES.moreFailed} Try again.
        </Alert>
      )}
      <LoadMore
        hasMore={feed.hasMore}
        loading={feed.loadingMore}
        onClick={feed.loadMore}
        endLabel={NOTIFICATION_MESSAGES.endLabel}
      />
    </>
  );
}
