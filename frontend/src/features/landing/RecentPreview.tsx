"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { EmptyState } from "@/components/ui/EmptyState";
import { PostCard } from "@/features/posts/PostCard";
import { PostCardSkeleton } from "@/features/posts/PostCardSkeleton";
import { toPostCardProps } from "@/features/posts/post-card-props";
import { fetchRecentFeed } from "@/features/posts/posts-api";
import type { Post } from "@/lib/api/types";

const PREVIEW_COUNT = 4;

type State = { kind: "loading" } | { kind: "error" } | { kind: "ready"; posts: Post[] };

/**
 * Four recent public posts (Stitch a1 "LiveClaimsFeed"), fetched in the browser so the page itself
 * stays prerendered. A removed post and a repost entry are left out. No action bar: signing up is
 * the next step.
 */
export function RecentPreview() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchRecentFeed(null, controller.signal)
      .then((page) => {
        const posts = page.items
          .flatMap((item) => (item.kind === "post" ? [item.post] : []))
          .filter((post) => post.status !== "removed");
        setState({ kind: "ready", posts: posts.slice(0, PREVIEW_COUNT) });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      });
    return () => controller.abort();
  }, []);

  return (
    <section
      aria-labelledby="recent-heading"
      className="mx-auto mb-space-xl max-w-wide px-space-lg"
    >
      <div className="mb-space-lg flex flex-col justify-between gap-space-sm sm:flex-row sm:items-end">
        <div>
          <h2 id="recent-heading" className="font-headline-md text-headline-md text-on-surface">
            Recent posts
          </h2>
          <p className="mt-space-xs font-body-sm text-body-sm text-on-surface-variant">
            The newest public posts, with their labels.
          </p>
        </div>
        <Link
          href="/home"
          className="font-body-sm text-body-sm font-semibold text-secondary hover:underline"
        >
          See more posts
        </Link>
      </div>
      {state.kind === "loading" && (
        <div className="grid grid-cols-1 gap-space-lg md:grid-cols-2" aria-busy="true">
          {Array.from({ length: PREVIEW_COUNT }, (_, i) => (
            <PostCardSkeleton key={i} />
          ))}
        </div>
      )}
      {state.kind === "error" && (
        <Alert tone="neutral">Recent posts couldn’t be loaded right now.</Alert>
      )}
      {state.kind === "ready" && state.posts.length === 0 && (
        <EmptyState icon="forum" title="No posts yet">
          Be the first to post.
        </EmptyState>
      )}
      {state.kind === "ready" && state.posts.length > 0 && (
        <div className="grid grid-cols-1 gap-space-lg md:grid-cols-2">
          {state.posts.map((post) => (
            <PostCard key={post.id} {...toPostCardProps(post)} />
          ))}
        </div>
      )}
    </section>
  );
}
