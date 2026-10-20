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
import { RemovedPostCard } from "./RemovedPostCard";
import { isUnavailable, visibleItems } from "./feed-items";
import { feedErrorMessage, POST_MESSAGES } from "./messages";
import { toPostCardProps } from "./post-card-props";
import { applyStatus, type StatusOverlay } from "./status-overlay";
import { feedItemKey } from "./posts-api";
import type { CursorFeed } from "./useCursorFeed";

/**
 * One card with its action bar (Part 7, 7B) and, for a repost, "Reposted by" above it. Exported for
 * the pinned emergencies above the feed (Part 11C), so their cards work the same way.
 */
export function FeedCard({
  post,
  reposter,
  overlay,
  highlight,
}: {
  post: Post;
  reposter: UserSummary | null;
  overlay: StatusOverlay;
  /** Search terms to mark in the claim (Part 12). */
  highlight?: string[];
}) {
  const shown = applyStatus(post, overlay);
  // Removed (loaded so, or found so by the poll): a tombstone for everyone, and for the author on
  // their own profile their words, the reason and the appeal. Never the card or its action bar.
  if (shown.status === "removed") return <RemovedPostCard post={shown} />;
  return (
    <PostCard
      {...toPostCardProps(shown)}
      header={reposter ? <RepostHeader user={reposter} /> : undefined}
      actions={<PostActions post={shown} />}
      highlight={highlight}
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
  alreadyShown,
  highlight,
  endLabel = "You're caught up.",
}: {
  /** Any feed of items; its first-page `head` (the pinned emergencies) is the caller's. */
  feed: CursorFeed<FeedItem, unknown>;
  /** Polled statuses laid over the loaded posts (Part 5): a badge changes without a reload. */
  statusUpdates?: StatusOverlay;
  /** Posts the poll found deleted: they disappear. */
  gone?: ReadonlySet<string>;
  /** What an empty list says (the Following tab and profiles word it differently). */
  empty?: ReactNode;
  /** Posts shown above the list (the pinned emergencies): never repeated in it. */
  alreadyShown?: ReadonlySet<string>;
  /** Search terms to mark in each claim (Part 12). */
  highlight?: string[];
  /** The line at the end of the list (search says it stops at 100 results). */
  endLabel?: ReactNode;
}) {
  const { phase } = feed;
  const items = visibleItems(feed.items, gone, alreadyShown);

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
          return (
            <FeedCard
              key={key}
              post={item.post}
              reposter={null}
              overlay={statusUpdates}
              highlight={highlight}
            />
          );
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
          <FeedCard
            key={key}
            post={original}
            reposter={item.reposted_by}
            overlay={statusUpdates}
            highlight={highlight}
          />
        );
      })}
      {feed.moreError !== null && <Alert tone="error">{POST_MESSAGES.moreFailed} Try again.</Alert>}
      <LoadMore
        hasMore={feed.hasMore}
        loading={feed.loadingMore}
        onClick={feed.loadMore}
        endLabel={endLabel}
      />
    </div>
  );
}
