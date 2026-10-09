"use client";

import { useEffect, useMemo } from "react";
import { EmptyState } from "@/components/ui/EmptyState";
import { FeedList } from "@/features/posts/FeedList";
import { useComposer } from "@/features/posts/ComposerProvider";
import { feedItemKey } from "@/features/posts/posts-api";
import { pendingPostIds } from "@/features/posts/status-overlay";
import { useCursorFeed } from "@/features/posts/useCursorFeed";
import { useStatusPolling } from "@/features/posts/useStatusPolling";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fetchUserPosts, type PostFilter } from "./social-api";

/**
 * One person's posts (the public ones), newest first. Mount it with a `key` that includes the
 * username and the filter: `useCursorFeed` doesn't refetch when `fetchPage` changes. "CHECKING
 * FACTS…" badges update by themselves, as on the home feed (Part 5). On your own profile a post you
 * make is added at the top when it matches the filter.
 */
export function ProfilePosts({
  username,
  filter,
  isMe,
  name,
}: {
  username: string;
  filter: PostFilter;
  isMe: boolean;
  name: string;
}) {
  const { status, user } = useAuth();
  const composer = useComposer();
  const feed = useCursorFeed({
    fetchPage: (cursor, signal) => fetchUserPosts(username, filter, cursor, signal),
    keyOf: feedItemKey,
    enabled: status !== "loading",
    resetKey: user?.id ?? null,
  });
  const { prepend } = feed;
  const pendingIds = useMemo(() => pendingPostIds(feed.items), [feed.items]);
  const polling = useStatusPolling(pendingIds);

  useEffect(() => {
    if (!isMe) return;
    return composer.onPosted((post) => {
      if (filter !== "all" && post.post_type !== filter) return;
      prepend({ kind: "post", post, reposted_by: null, activity_at: post.created_at });
    });
  }, [composer, prepend, isMe, filter]);

  const what = filter === "fact" ? "fact posts" : filter === "opinion" ? "opinions" : "posts";
  const empty = (
    <EmptyState icon="forum" title={`No ${what} yet`}>
      {isMe ? `You haven't shared any ${what} yet.` : `${name} hasn't shared any ${what} yet.`}
    </EmptyState>
  );

  return <FeedList feed={feed} statusUpdates={polling.updates} gone={polling.gone} empty={empty} />;
}
