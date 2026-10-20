"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { fetchFollowingFeed } from "@/features/social/social-api";
import type { FeedItem, Post } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { emergencyShown } from "@/lib/post-display";
import { ComposerTrigger } from "./ComposerTrigger";
import { useComposer } from "./ComposerProvider";
import { FeedCard, FeedList } from "./FeedList";
import { PinnedEmergencies } from "./PinnedEmergencies";
import { type FeedHead, feedItemKey, fetchRecentFeed } from "./posts-api";
import { applyStatus, pendingPostIds } from "./status-overlay";
import { useCursorFeed } from "./useCursorFeed";
import { useStatusPolling } from "./useStatusPolling";

type HomeTab = "recent" | "following";

const RECENT_TAB = { id: "recent", label: "Recent" };
const FOLLOWING_TAB = { id: "following", label: "Following" };
const PREFIX = "home-feed";

interface Pinned {
  posts: Post[];
  total: number;
  ids: ReadonlySet<string>;
}

/** A feed's pinned emergencies: the ones you just made first, then the first page's. */
function mergePinned(own: readonly Post[], head: FeedHead | null): Pinned {
  const fromServer = head?.pinned ?? [];
  const serverIds = new Set(fromServer.map((post) => post.id));
  const extra = own.filter((post) => !serverIds.has(post.id));
  const posts = [...extra, ...fromServer];
  return {
    posts,
    total: (head?.pinnedTotal ?? 0) + extra.length,
    ids: new Set(posts.map((post) => post.id)),
  };
}

const NO_OTHER_POSTS = (
  <EmptyState icon="forum" title="No other posts yet">
    The emergency posts above are all there is for now.
  </EmptyState>
);

/**
 * `/home` (Stitch b1): the composer trigger and two feeds. Recent (public, newest first) is the
 * first tab and the default, for everyone. Following (the people you follow and you) is a second
 * tab for signed-in users and loads on first use, so `/home` makes no extra request. A post made in
 * the composer is added at the top of both without refetching (insert on success).
 *
 * Each tab pins its active emergencies above its list (`PinnedEmergencies`, Part 11C), from its first
 * page's `pinned`; an emergency you just made goes there (on both tabs) instead of into the lists.
 * A pinned post the poll finds FALSE or removed leaves the section; none is repeated below.
 */
export function HomeFeed() {
  const { status, user } = useAuth();
  const composer = useComposer();
  const [tab, setTab] = useState<HomeTab>("recent");
  // Stays true once the Following tab was opened, so switching back keeps the loaded list.
  const [followingOpened, setFollowingOpened] = useState(false);
  const signedIn = status === "authenticated";

  const recent = useCursorFeed<FeedItem, FeedHead>({
    fetchPage: fetchRecentFeed,
    keyOf: feedItemKey,
    // A first request before the session is known would go out without the token.
    enabled: status !== "loading",
    resetKey: user?.id ?? null,
  });
  const following = useCursorFeed<FeedItem, FeedHead>({
    fetchPage: fetchFollowingFeed,
    keyOf: feedItemKey,
    enabled: signedIn && followingOpened,
    resetKey: user?.id ?? null,
  });

  // Emergencies you just made: pinned on both tabs at once. Another person's are not yours.
  const [ownEmergencies, setOwnEmergencies] = useState<Post[]>([]);
  const owner = user?.id ?? null;
  const [emergenciesOwner, setEmergenciesOwner] = useState(owner);
  if (emergenciesOwner !== owner) {
    setEmergenciesOwner(owner);
    setOwnEmergencies([]);
  }
  const recentPinned = useMemo(
    () => mergePinned(ownEmergencies, recent.head),
    [ownEmergencies, recent.head],
  );
  const followingPinned = useMemo(
    () => mergePinned(ownEmergencies, following.head),
    [ownEmergencies, following.head],
  );

  const active: HomeTab = signedIn && tab === "following" ? "following" : "recent";
  const activeFeed = active === "following" ? following : recent;
  const activePinned = active === "following" ? followingPinned : recentPinned;
  // "CHECKING FACTS…" badges update by themselves (Part 5): the tab you are looking at is polled,
  // its pinned emergencies included.
  const pendingIds = useMemo(() => {
    const ids = new Set(pendingPostIds(activeFeed.items));
    for (const post of activePinned.posts) if (post.status === "pending") ids.add(post.id);
    return [...ids];
  }, [activeFeed.items, activePinned.posts]);
  const polling = useStatusPolling(pendingIds);
  const { updates, gone } = polling;

  const { prepend: prependRecent } = recent;
  const { prepend: prependFollowing } = following;
  useEffect(
    () =>
      composer.onPosted((post) => {
        if (post.emergency_active) {
          setOwnEmergencies((list) => [post, ...list.filter((other) => other.id !== post.id)]);
          return;
        }
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

  // Out of the section: a pinned post the poll found deleted, FALSE or removed.
  const hidePinned = useCallback(
    (post: Post) => gone.has(post.id) || !emergencyShown(applyStatus(post, updates)),
    [gone, updates],
  );
  const pinnedCard = useCallback(
    (post: Post) => <FeedCard post={post} reposter={null} overlay={updates} />,
    [updates],
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
        <div className="flex flex-col gap-space-lg">
          <PinnedEmergencies
            feed="recent"
            posts={recentPinned.posts}
            total={recentPinned.total}
            renderCard={pinnedCard}
            hide={hidePinned}
          />
          <FeedList
            feed={recent}
            statusUpdates={updates}
            gone={gone}
            alreadyShown={recentPinned.ids}
            empty={recentPinned.posts.length > 0 ? NO_OTHER_POSTS : undefined}
          />
        </div>
      </TabPanel>
      {signedIn && (
        <TabPanel idPrefix={PREFIX} tab="following" selected={active === "following"}>
          {followingOpened && (
            <div className="flex flex-col gap-space-lg">
              <PinnedEmergencies
                feed="following"
                posts={followingPinned.posts}
                total={followingPinned.total}
                renderCard={pinnedCard}
                hide={hidePinned}
              />
              <FeedList
                feed={following}
                statusUpdates={updates}
                gone={gone}
                alreadyShown={followingPinned.ids}
                empty={followingPinned.posts.length > 0 ? NO_OTHER_POSTS : followingEmpty}
              />
            </div>
          )}
        </TabPanel>
      )}
    </div>
  );
}
