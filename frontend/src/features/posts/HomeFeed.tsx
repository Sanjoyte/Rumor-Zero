"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { fetchFollowingFeed } from "@/features/social/social-api";
import type { FeedItem } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { ComposerTrigger } from "./ComposerTrigger";
import { useComposer } from "./ComposerProvider";
import { FeedList } from "./FeedList";
import { feedItemKey, fetchRecentFeed } from "./posts-api";
import { pendingPostIds } from "./status-overlay";
import { useCursorFeed } from "./useCursorFeed";
import { useStatusPolling } from "./useStatusPolling";

type HomeTab = "recent" | "following";

const RECENT_TAB = { id: "recent", label: "Recent" };
const FOLLOWING_TAB = { id: "following", label: "Following" };
const PREFIX = "home-feed";

/**
 * `/home` (Stitch b1): the composer trigger and two feeds. Recent (public, newest first) is the
 * first tab and the default, for everyone. Following (the people you follow and you) is a second
 * tab for signed-in users and loads on first use, so `/home` makes no extra request. A post made in
 * the composer is added at the top of both without refetching (insert on success).
 */
export function HomeFeed() {
  const { status, user } = useAuth();
  const composer = useComposer();
  const [tab, setTab] = useState<HomeTab>("recent");
  // Stays true once the Following tab was opened, so switching back keeps the loaded list.
  const [followingOpened, setFollowingOpened] = useState(false);
  const signedIn = status === "authenticated";

  const recent = useCursorFeed({
    fetchPage: fetchRecentFeed,
    keyOf: feedItemKey,
    // A first request before the session is known would go out without the token.
    enabled: status !== "loading",
    resetKey: user?.id ?? null,
  });
  const following = useCursorFeed({
    fetchPage: fetchFollowingFeed,
    keyOf: feedItemKey,
    enabled: signedIn && followingOpened,
    resetKey: user?.id ?? null,
  });

  const active: HomeTab = signedIn && tab === "following" ? "following" : "recent";
  const activeFeed = active === "following" ? following : recent;
  // "CHECKING FACTS…" badges update by themselves (Part 5): the tab you are looking at is polled.
  const pendingIds = useMemo(() => pendingPostIds(activeFeed.items), [activeFeed.items]);
  const polling = useStatusPolling(pendingIds);

  const { prepend: prependRecent } = recent;
  const { prepend: prependFollowing } = following;
  useEffect(
    () =>
      composer.onPosted((post) => {
        const item: FeedItem = {
          kind: "post",
          post,
          reposted_by: null,
          activity_at: post.created_at,
        };
        prependRecent(item);
        prependFollowing(item);
      }),
    [composer, prependRecent, prependFollowing],
  );

  function choose(id: string) {
    const next = id === "following" ? "following" : "recent";
    if (next === "following") setFollowingOpened(true);
    setTab(next);
  }

  const followingEmpty = (
    <EmptyState
      icon="group"
      title="Follow people to see their posts here"
      action={
        <Button variant="secondary" onClick={() => choose("recent")}>
          See Recent
        </Button>
      }
    >
      Posts by the people you follow, and your own, show up in this tab.
    </EmptyState>
  );

  return (
    <div className="mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg">
      <h1 className="sr-only">Home</h1>
      <Tabs
        tabs={signedIn ? [RECENT_TAB, FOLLOWING_TAB] : [RECENT_TAB]}
        value={active}
        onChange={choose}
        label="Feed"
        idPrefix={PREFIX}
      />
      <ComposerTrigger />
      <TabPanel idPrefix={PREFIX} tab="recent" selected={active === "recent"}>
        <FeedList feed={recent} statusUpdates={polling.updates} gone={polling.gone} />
      </TabPanel>
      {signedIn && (
        <TabPanel idPrefix={PREFIX} tab="following" selected={active === "following"}>
          {followingOpened && (
            <FeedList
              feed={following}
              statusUpdates={polling.updates}
              gone={polling.gone}
              empty={followingEmpty}
            />
          )}
        </TabPanel>
      )}
    </div>
  );
}
