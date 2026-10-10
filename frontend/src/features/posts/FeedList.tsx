"use client";

import type { ReactNode } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadMore } from "@/components/ui/LoadMore";
import type { FeedItem, Post } from "@/lib/api/types";
import { PostActions } from "@/features/social/PostActions";
import { PostCard } from "./PostCard";
import { PostCardSkeleton } from "./PostCardSkeleton";
import { feedErrorMessage, POST_MESSAGES } from "./messages";
import { toPostCardProps } from "./post-card-props";
import { applyStatus, type StatusOverlay } from "./status-overlay";
import { feedItemKey } from "./posts-api";
import type { CursorFeed } from "./useCursorFeed";

/** One card with its like and comment bar (Part 7). */
function FeedCard({ post, overlay }: { post: Post; overlay: StatusOverlay }) {
  const shown = applyStatus(post, overlay);
  return (
    <PostCard
      {...toPostCardProps(shown)}
      actions={
        <PostActions
          postId={shown.id}
          liked={shown.liked_by_me}
          likeCount={shown.like_count}
          commentCount={shown.comment_count}
        />
      }
    />
  );
}

/**
 * A feed of post cards (b1): skeletons while the first page loads, an error with "Try again", an
 * empty state, the cards, and Load more with b1's "You're caught up." end line. A failed Load more
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
  const items = gone
    ? feed.items.filter((i) => i.kind !== "post" || !gone.has(i.post.id))
    : feed.items;

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

  if (items.length === 0) {
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
      {items.map((item) =>
        // Reposts arrive in Part 7B (Following and profiles; never in Recent).
        item.kind === "post" ? (
          <FeedCard key={feedItemKey(item)} post={item.post} overlay={statusUpdates} />
        ) : null,
      )}
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
