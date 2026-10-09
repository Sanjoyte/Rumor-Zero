"use client";

import { useEffect, useMemo } from "react";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { useAuth } from "@/lib/auth/AuthProvider";
import { ComposerTrigger } from "./ComposerTrigger";
import { useComposer } from "./ComposerProvider";
import { FeedList } from "./FeedList";
import { feedItemKey, fetchRecentFeed } from "./posts-api";
import { pendingPostIds } from "./status-overlay";
import { useCursorFeed } from "./useCursorFeed";
import { useStatusPolling } from "./useStatusPolling";

const TABS = [{ id: "recent", label: "Recent" }];
const PREFIX = "home-feed";

/**
 * `/home` (Stitch b1): the composer trigger and the public Recent feed, newest first. A post made
 * in the composer is added at the top without refetching (insert on success). Following arrives
 * in Part 6 as a second tab.
 */
export function HomeFeed() {
  const { status, user } = useAuth();
  const composer = useComposer();
  const feed = useCursorFeed({
    fetchPage: fetchRecentFeed,
    keyOf: feedItemKey,
    // A first request before the session is known would go out without the token.
    enabled: status !== "loading",
    resetKey: user?.id ?? null,
  });
  const { prepend } = feed;
  // "CHECKING FACTS…" badges update by themselves (Part 5): visible tab only, 10 s backing off to 60 s.
  const pendingIds = useMemo(() => pendingPostIds(feed.items), [feed.items]);
  const polling = useStatusPolling(pendingIds);

  useEffect(
    () =>
      composer.onPosted((post) =>
        prepend({ kind: "post", post, reposted_by: null, activity_at: post.created_at }),
      ),
    [composer, prepend],
  );

  return (
    <div className="mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg">
      <h1 className="sr-only">Home</h1>
      <Tabs tabs={TABS} value="recent" onChange={() => {}} label="Feed" idPrefix={PREFIX} />
      <ComposerTrigger />
      <TabPanel idPrefix={PREFIX} tab="recent" selected>
        <FeedList feed={feed} statusUpdates={polling.updates} gone={polling.gone} />
      </TabPanel>
    </div>
  );
}
