"use client";

import { useMemo } from "react";
import { EmptyState } from "@/components/ui/EmptyState";
import { FeedList } from "@/features/posts/FeedList";
import { feedItemKey } from "@/features/posts/posts-api";
import { pendingPostIds } from "@/features/posts/status-overlay";
import { useCursorFeed } from "@/features/posts/useCursorFeed";
import { useStatusPolling } from "@/features/posts/useStatusPolling";
import { useAuth } from "@/lib/auth/AuthProvider";
import { queryTerms } from "./highlight";
import { SEARCH_MESSAGES, SEARCH_RESULT_CAP } from "./messages";
import { searchPosts } from "./search-api";
import type { SearchFilter } from "./search-params";

/**
 * The post results for one query and chip, best match first. Mount it with a `key` that includes
 * both: `useCursorFeed` doesn't refetch when `fetchPage` changes. The cards are the feed's own
 * (`FeedList`), with the query's words marked, and "CHECKING FACTS…" badges update by themselves
 * (a pending fact is searchable). The list ends at 100 results and says so.
 */
export function PostResults({ q, filter }: { q: string; filter: SearchFilter }) {
  const { status, user } = useAuth();
  const feed = useCursorFeed({
    fetchPage: (cursor, signal) => searchPosts(q, filter, cursor, signal),
    keyOf: feedItemKey,
    enabled: status !== "loading",
    resetKey: user?.id ?? null,
  });
  const terms = useMemo(() => queryTerms(q), [q]);
  const pendingIds = useMemo(() => pendingPostIds(feed.items), [feed.items]);
  const polling = useStatusPolling(pendingIds);
  // Shown only once there is nothing more to load, so "100 or more" is "the cap was reached".
  const capped = feed.items.length >= SEARCH_RESULT_CAP;

  return (
    <FeedList
      feed={feed}
      statusUpdates={polling.updates}
      gone={polling.gone}
      highlight={terms}
      endLabel={capped ? SEARCH_MESSAGES.capped : SEARCH_MESSAGES.caughtUp}
      empty={
        <EmptyState icon="search_off" title={SEARCH_MESSAGES.noPostsTitle(q)}>
          {SEARCH_MESSAGES.noPostsBody}
        </EmptyState>
      }
    />
  );
}
