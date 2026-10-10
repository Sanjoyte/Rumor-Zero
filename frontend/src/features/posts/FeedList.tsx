"use client";

import { type ReactNode, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadMore } from "@/components/ui/LoadMore";
import { useToast } from "@/components/ui/Toast";
import type { FeedItem, Post, UserSummary } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { repostFailureMessage, SOCIAL_MESSAGES } from "@/features/social/messages";
import { PostActions } from "@/features/social/PostActions";
import { RepostHeader } from "@/features/social/RepostHeader";
import { unrepostPost } from "@/features/social/social-api";
import { UnavailablePostCard } from "@/features/social/UnavailablePostCard";
import { PostCard } from "./PostCard";
import { PostCardSkeleton } from "./PostCardSkeleton";
import { isUnavailable, visibleItems } from "./feed-items";
import { feedErrorMessage, POST_MESSAGES } from "./messages";
import { toPostCardProps } from "./post-card-props";
import { applyStatus, type StatusOverlay } from "./status-overlay";
import { feedItemKey } from "./posts-api";
import type { CursorFeed } from "./useCursorFeed";

/** One card with its action bar (Part 7, 7B) and, for a repost, "Reposted by" above it. */
function FeedCard({
  post,
  reposter,
  overlay,
}: {
  post: Post;
  reposter: UserSummary | null;
  overlay: StatusOverlay;
}) {
  const shown = applyStatus(post, overlay);
  return (
    <PostCard
      {...toPostCardProps(shown)}
      header={reposter ? <RepostHeader user={reposter} /> : undefined}
      actions={<PostActions post={shown} />}
    />
  );
}

/**
 * A repost whose original is gone. When the repost is yours it can be undone, and the item leaves
 * the list at once (the server answers 204 whatever became of the original).
 */
function UnavailableRepost({
  reposter,
  postId,
  onRemoved,
}: {
  reposter: UserSummary;
  postId: string;
  onRemoved: () => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const [undoing, setUndoing] = useState(false);

  async function undo() {
    setUndoing(true);
    try {
      await unrepostPost(postId);
    } catch (error) {
      setUndoing(false);
      toast.show(repostFailureMessage(error, true), { tone: "error" });
      return;
    }
    onRemoved();
    toast.show(SOCIAL_MESSAGES.repostUndone);
  }

  return (
    <UnavailablePostCard
      reposter={reposter}
      onUndo={user?.id === reposter.id ? () => void undo() : undefined}
      undoing={undoing}
    />
  );
}

/**
 * A feed of post cards (b1): skeletons while the first page loads, an error with "Try again", an
 * empty state, the cards (a repost has "Reposted by" above it, or says its original is gone), and
 * Load more with b1's "You're caught up." end line. A failed Load more
 * keeps the list and shows an inline error beside the button, which tries again.
 */
export function FeedList({
  feed,
  statusUpdates = {},
  gone,
  empty,
}: {
  feed: CursorFeed<FeedItem>;
  /** Polled statuses laid over the loaded posts (Part 5): a badge changes without a reload. */
  statusUpdates?: StatusOverlay;
  /** Posts the poll found deleted: they disappear. */
  gone?: ReadonlySet<string>;
  /** What an empty list says (the Following tab and profiles word it differently). */
  empty?: ReactNode;
}) {
  const { phase } = feed;
  const items = visibleItems(feed.items, gone);

  if (phase === "idle" || phase === "loading") {
    return (
      <div aria-busy="true" className="flex flex-col gap-space-lg">
        <span className="sr-only">Loading posts…</span>
        <PostCardSkeleton />
        <PostCardSkeleton />
        <PostCardSkeleton />
      </div>
    );
  }

  if (phase === "error") {
    return (
      <Alert tone="error" title="Couldn't load posts">
        <p>{feedErrorMessage(feed.error)}</p>
        <Button variant="secondary" onClick={feed.retry} className="mt-space-md">
          Try again
        </Button>
      </Alert>
    );
  }

  // A page can come back empty with a next page behind it (a cached page whose reposts were
  // undone, or posts deleted since): offer "Load more" instead of claiming there is nothing.
  if (items.length === 0 && !feed.hasMore) {
    return (
      empty ?? (
        <EmptyState icon="forum" title="No posts yet">
          Be the first to post something.
        </EmptyState>
      )
    );
  }

  return (
    <div className="flex flex-col gap-space-lg">
      {items.map((item) => {
        const key = feedItemKey(item);
        if (item.kind === "post") {
          return <FeedCard key={key} post={item.post} reposter={null} overlay={statusUpdates} />;
        }
        const original = item.post;
        // The original is gone: deleted, removed, or just found so by the poll.
        const lost =
          isUnavailable(original) ||
          gone?.has(original.id) === true ||
          statusUpdates[original.id]?.status === "removed";
        return lost ? (
          <UnavailableRepost
            key={key}
            reposter={item.reposted_by}
            postId={original.id}
            onRemoved={() => feed.remove(key)}
          />
        ) : (
          <FeedCard key={key} post={original} reposter={item.reposted_by} overlay={statusUpdates} />
        );
      })}
      {feed.moreError !== null && <Alert tone="error">{POST_MESSAGES.moreFailed} Try again.</Alert>}
      <LoadMore
        hasMore={feed.hasMore}
        loading={feed.loadingMore}
        onClick={feed.loadMore}
        endLabel="You're caught up."
      />
    </div>
  );
}
