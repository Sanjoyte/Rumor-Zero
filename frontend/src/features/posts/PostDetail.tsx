"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { AppealPendingBadge, EmergencyBadge, StatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { VerdictStripe } from "@/components/ui/VerdictStripe";
import type { Post } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatFullDateTime } from "@/lib/format";
import { stripeTone } from "@/lib/post-display";
import { AppealButton } from "@/features/appeals/AppealButton";
import { AppealOutcome } from "@/features/appeals/AppealOutcome";
import { CommentSection } from "@/features/social/CommentSection";
import { PostActions } from "@/features/social/PostActions";
import { CopyLinkButton } from "./CopyLinkButton";
import { DeletePostModal } from "./DeletePostModal";
import { RemovedPostCard } from "./RemovedPostCard";
import { SourceList } from "./SourceList";
import { REMOVED_MESSAGES } from "./Tombstone";
import { VerdictBlock } from "./VerdictBlock";
import { usePostDetail } from "./usePostDetail";
import { useStatusPolling } from "./useStatusPolling";

export const DETAIL_MESSAGES = {
  deleted: "Post deleted.",
  removed: REMOVED_MESSAGES.page,
  notFound: "The post may have been deleted, or the link may be wrong.",
  loadFailed: "Couldn't load this post. Check your connection and try again.",
} as const;

const CONTAINER =
  "mx-auto flex w-full max-w-reading flex-col gap-space-xl px-margin-mobile py-space-xl md:px-space-lg";

/** A removed post reaches everyone but its author blanked (ARCHITECTURE §9): show the notice. */
export function isTombstone(post: Post): boolean {
  return post.status === "removed" && !post.is_mine;
}

function BackLink() {
  return (
    <Link
      href="/home"
      prefetch={false}
      className="inline-flex items-center gap-space-xs self-start font-label-code text-label-code tracking-wider text-secondary uppercase transition-colors hover:text-on-secondary-container hover:underline"
    >
      <Icon name="arrow_back" size="md" />
      Back to Home
    </Link>
  );
}

function AuthorRow({ post }: { post: Post }) {
  const hasName = post.author.display_name.trim() !== "";
  const name = hasName ? post.author.display_name : `@${post.author.username}`;
  return (
    <Link
      href={`/u/${post.author.username}`}
      prefetch={false}
      className="group flex items-center gap-space-md self-start rounded-lg focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none"
    >
      <Avatar name={name} src={post.author.avatar_url} size={10} decorative />
      <div className="flex min-w-0 flex-col">
        <span className="truncate font-body-md text-body-md font-semibold text-on-surface group-hover:underline">
          {name}
        </span>
        <span className="flex flex-wrap items-center gap-space-xs font-label-code text-label-code text-outline">
          {hasName && <span className="truncate">@{post.author.username}</span>}
          {hasName && <span aria-hidden="true">•</span>}
          <time dateTime={post.created_at}>{formatFullDateTime(post.created_at)}</time>
        </span>
      </div>
    </Link>
  );
}

/**
 * `/p/[id]` (Stitch b3: claim header, author row, verdict, sources, actions). The claim and its
 * status arrive server-rendered; the rest is client-side, including the like button and the
 * discussion (Part 7), repost and bookmark (7B), report (8), appeal (11). 11D adds stats. A removed
 * post is `RemovedPostCard`: a tombstone for everyone but its author, who sees their words and can
 * appeal; it has no action bar, verdict or discussion.
 */
export function PostDetail({ id, initial }: { id: string; initial: Post | null }) {
  const router = useRouter();
  const toast = useToast();
  const detail = usePostDetail(id, initial);
  const { post, phase, patch, reload } = detail;
  const [confirmDelete, setConfirmDelete] = useState(false);

  // A pending fact checks itself: the badge changes at once, then one quiet refetch brings the rest.
  const pendingIds = useMemo(() => (post?.status === "pending" ? [id] : []), [post?.status, id]);
  const polling = useStatusPolling(pendingIds);
  const update = polling.updates[id];
  const gone = polling.gone.has(id);
  useEffect(() => {
    if (!update || update.status === post?.status) return;
    patch({
      status: update.status,
      confidence_score: update.confidence_score,
      verdict_source: update.verdict_source,
    });
    reload();
  }, [update, post?.status, patch, reload]);
  useEffect(() => {
    if (gone) reload();
  }, [gone, reload]);

  function onDeleted() {
    toast.show(DETAIL_MESSAGES.deleted, { tone: "success" });
    router.replace("/home");
  }

  if (phase === "loading") {
    return (
      <div aria-busy="true" className={CONTAINER}>
        <span className="sr-only">Loading post…</span>
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (phase === "error" || !post) {
    const missing = phase === "not-found";
    return (
      <div className={CONTAINER}>
        <BackLink />
        {missing ? (
          <EmptyState
            icon="search_off"
            title="Post not found"
            action={
              <Link
                href="/home"
                prefetch={false}
                className="font-body-md text-body-md font-semibold text-secondary hover:underline"
              >
                Back to Home
              </Link>
            }
          >
            {DETAIL_MESSAGES.notFound}
          </EmptyState>
        ) : (
          <Alert tone="error" title="Couldn't load this post">
            <p>{DETAIL_MESSAGES.loadFailed}</p>
            <Button variant="secondary" onClick={detail.retry} className="mt-space-md">
              Try again
            </Button>
          </Alert>
        )}
      </div>
    );
  }

  const isFact = post.post_type === "fact";
  if (post.status === "removed") {
    return (
      <div className={CONTAINER}>
        <BackLink />
        <RemovedPostCard
          post={post}
          layout="page"
          authorRow={<AuthorRow post={post} />}
          footer={
            post.is_mine && (
              <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
                <Icon name="delete" size="lg" />
                Delete
              </Button>
            )
          }
          onFiled={patch}
          onStale={reload}
        />
        {post.is_mine && isFact && <SourceList sources={post.sources} />}
        {post.is_mine && (
          <DeletePostModal
            open={confirmDelete}
            postId={post.id}
            isFact={isFact}
            onClose={() => setConfirmDelete(false)}
            onDeleted={onDeleted}
          />
        )}
      </div>
    );
  }

  const tone = stripeTone({ status: post.status, emergencyActive: post.emergency_active });
  return (
    <div className={CONTAINER}>
      <BackLink />
      <Card as="article" className="flex flex-col gap-space-lg p-space-xl">
        {tone && <VerdictStripe tone={tone} />}
        <div className="flex flex-wrap items-center gap-space-sm">
          <CategoryChip type={post.post_type} />
          <StatusBadge
            status={post.status}
            verdictSource={post.verdict_source}
            confidenceScore={post.confidence_score}
          />
          {post.appeal_status === "open" && <AppealPendingBadge />}
          {post.emergency_active && <EmergencyBadge />}
        </div>
        <h1
          className={cn(
            "text-headline-md leading-tight tracking-tight break-words whitespace-pre-wrap text-on-surface",
            isFact ? "font-claim-headline" : "font-claim-opinion italic",
          )}
        >
          {"“"}
          {post.content}
          {"”"}
        </h1>
        <AuthorRow post={post} />
        <div className="flex flex-wrap items-center gap-x-space-lg gap-y-space-sm border-t border-outline-variant/30 pt-space-md">
          <PostActions variant="detail" post={post} />
          <CopyLinkButton postId={post.id} />
          {post.is_mine && (
            <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
              <Icon name="delete" size="lg" />
              Delete
            </Button>
          )}
        </div>
      </Card>
      <VerdictBlock
        post={post}
        footer={
          post.is_mine && post.can_appeal ? (
            <AppealButton post={post} onFiled={patch} onStale={reload} />
          ) : undefined
        }
      />
      {post.is_mine && <AppealOutcome post={post} />}
      {isFact && <SourceList sources={post.sources} />}
      <CommentSection
        key={post.id}
        postId={post.id}
        count={post.comment_count}
        onCountChange={(count) => patch({ comment_count: count })}
      />
      {post.is_mine && (
        <DeletePostModal
          open={confirmDelete}
          postId={post.id}
          isFact={isFact}
          onClose={() => setConfirmDelete(false)}
          onDeleted={onDeleted}
        />
      )}
    </div>
  );
}
