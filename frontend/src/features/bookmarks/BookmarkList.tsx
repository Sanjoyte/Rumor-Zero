"use client";

import { useMemo } from "react";
import { EmptyState } from "@/components/ui/EmptyState";
import { FeedList } from "@/features/posts/FeedList";
import { feedItemKey } from "@/features/posts/posts-api";
import { pendingPostIds } from "@/features/posts/status-overlay";
import { useCursorFeed } from "@/features/posts/useCursorFeed";
import { useStatusPolling } from "@/features/posts/useStatusPolling";
import { fetchBookmarks } from "@/features/social/social-api";
import { useAuth } from "@/lib/auth/AuthProvider";

const CONTAINER =
  "mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg";

/**
 * `/bookmarks`: the posts you saved, newest bookmark first (ARCHITECTURE §4d). Private: the API only
 * ever returns your own list, and nothing here counts anyone's bookmarks. The route guard has sent
 * visitors to log in, so the session is settled before the first request. A post you un-bookmark
 * here stays until the next load, as an unfollowed row does in a list (Part 6).
 */
export function BookmarkList() {
  const { status, user } = useAuth();
  const feed = useCursorFeed({
    fetchPage: fetchBookmarks,
    keyOf: feedItemKey,
    // A first request before the session is known would go out without the token.
    enabled: status === "authenticated",
    resetKey: user?.id ?? null,
  });
  const pendingIds = useMemo(() => pendingPostIds(feed.items), [feed.items]);
  const polling = useStatusPolling(pendingIds);

  const empty = (
    <EmptyState icon="bookmark" title="No bookmarks yet">
      Posts you bookmark appear here. Only you can see them.
    </EmptyState>
  );

  return (
    <div className={CONTAINER}>
      <h1 className="font-headline-lg text-headline-lg tracking-tight text-on-surface">
        Bookmarks
      </h1>
      <FeedList feed={feed} statusUpdates={polling.updates} gone={polling.gone} empty={empty} />
    </div>
  );
}
