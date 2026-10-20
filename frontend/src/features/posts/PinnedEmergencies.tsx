"use client";

import {
  type ReactNode,
  type Ref,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import type { Post } from "@/lib/api/types";
import { PostCard } from "./PostCard";
import { collapse, expand, parseCollapsed, readCollapsed, subscribe } from "./pinned-collapse";
import { toPostCardProps } from "./post-card-props";
import { fetchEmergencies, type PinnedFeed } from "./posts-api";
import { type CursorPage, useCursorFeed } from "./useCursorFeed";

const BANNER =
  "flex items-center justify-between gap-space-md rounded-lg border border-tertiary/30 bg-tertiary-fixed/30 text-on-surface";

function postKey(post: Post): string {
  return post.id;
}

function plainCard(post: Post): ReactNode {
  return <PostCard {...toPostCardProps(post)} />;
}

/** Nothing is stored before a click: the server render and the first client render agree. */
function noStoredValue(): string | null {
  return null;
}

/**
 * The folded section (user decision 2026-10-19): one line, "2 emergency posts pinned" and Show.
 * Exported for the `/dev/ui` gallery.
 */
export function PinnedEmergenciesBar({
  count,
  onShow,
  showRef,
}: {
  count: number;
  onShow: () => void;
  showRef?: Ref<HTMLButtonElement>;
}) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className={`${BANNER} px-space-md py-space-sm`}>
      <div className="flex min-w-0 items-center gap-space-sm">
        <Icon name="bolt" filled className="shrink-0 text-tertiary" />
        <h2 id={headingId} className="font-body-sm text-body-sm font-semibold text-on-surface">
          {count} emergency {count === 1 ? "post" : "posts"} pinned
        </h2>
      </div>
      <button
        ref={showRef}
        type="button"
        onClick={onShow}
        className="shrink-0 rounded-lg font-label-code text-label-code font-bold tracking-wide text-tertiary uppercase hover:underline focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none"
      >
        Show
      </button>
    </section>
  );
}

export interface PinnedEmergenciesProps {
  /** Which feed this section belongs to: its "Show all" list and its folded state. */
  feed: PinnedFeed;
  /** The pinned posts, newest first (the first page's, at most 3, plus one you just made). */
  posts: Post[];
  /** How many are pinned in all (`pinned_total`): "Show all (N)" when more than shown. */
  total: number;
  /** One card. The feed passes its own (the action bar, the polled status); plain cards by default. */
  renderCard?: (post: Post) => ReactNode;
  /** A post the poll found FALSE or removed: it leaves the section (the "Show all" list too). */
  hide?: (post: Post) => boolean;
  /** "Show all" loads the rest in place; replaceable for tests. */
  fetchAll?: (cursor: string | null, signal: AbortSignal) => Promise<CursorPage<Post>>;
}

/**
 * The pinned emergencies above a feed (Stitch b1's dispatch banner, copy rewritten under D8; Part
 * 11C): a `bolt` tile, "EMERGENCY POSTS", "Pinned for a limited time and checked first.", up to
 * three cards, "Show all (N)" when more are pinned, and × to fold it to one line for this tab.
 *
 * Presentational apart from "Show all" and the fold: the cards come from the caller, so the gallery
 * renders it without a session.
 */
export function PinnedEmergencies({
  feed,
  posts,
  total,
  renderCard = plainCard,
  hide,
  fetchAll,
}: PinnedEmergenciesProps) {
  const headingId = useId();
  const [showingAll, setShowingAll] = useState(false);
  const all = useCursorFeed<Post>({
    fetchPage: fetchAll ?? ((cursor, signal) => fetchEmergencies(feed, cursor, signal)),
    keyOf: postKey,
    enabled: showingAll,
    resetKey: feed,
  });
  const raw = useSyncExternalStore(subscribe, () => readCollapsed(feed), noStoredValue);
  const folded = useMemo(() => parseCollapsed(raw), [raw]);

  const pinned = hide ? posts.filter((post) => !hide(post)) : posts;
  const dropped = posts.length - pinned.length;
  const count = Math.max(total - dropped, pinned.length);
  const listed = showingAll && all.phase === "ready" ? all.items : pinned;
  const shown = hide ? listed.filter((post) => !hide(post)) : listed;
  // Folded until a post that wasn't pinned when × was pressed appears.
  const collapsed = pinned.length > 0 && pinned.every((post) => folded.has(post.id));

  // Where focus goes once the section has changed shape: × and Show replace each other.
  const hideRef = useRef<HTMLButtonElement>(null);
  const showRef = useRef<HTMLButtonElement>(null);
  const focusNext = useRef<"hide" | "show" | null>(null);
  useEffect(() => {
    const target = focusNext.current === "show" ? showRef : hideRef;
    if (focusNext.current) target.current?.focus();
    focusNext.current = null;
  }, [collapsed]);

  if (pinned.length === 0) return null;

  if (collapsed) {
    return (
      <PinnedEmergenciesBar
        count={count}
        showRef={showRef}
        onShow={() => {
          focusNext.current = "hide";
          expand(feed);
        }}
      />
    );
  }

  function fold() {
    focusNext.current = "show";
    collapse(feed, [...new Set([...pinned, ...shown].map(postKey))]);
  }

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-space-md">
      <div className={`${BANNER} p-space-md`}>
        <div className="flex min-w-0 items-center gap-space-md">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-tertiary/10 text-tertiary">
            <Icon name="bolt" size="lg" />
          </div>
          <div className="flex min-w-0 flex-col gap-space-xs sm:flex-row sm:items-center sm:gap-space-sm">
            <h2
              id={headingId}
              className="font-label-code text-label-code font-bold tracking-wider whitespace-nowrap text-tertiary uppercase"
            >
              Emergency posts
            </h2>
            <span aria-hidden="true" className="hidden text-outline-variant sm:inline">
              ·
            </span>
            <p className="font-body-sm text-body-sm text-on-surface">
              Pinned for a limited time and checked first.
            </p>
          </div>
        </div>
        <button
          ref={hideRef}
          type="button"
          aria-label="Hide the emergency posts"
          title="Hide the emergency posts"
          onClick={fold}
          className="shrink-0 rounded-lg p-0.5 text-outline transition-colors hover:text-on-surface focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none"
        >
          <Icon name="close" size="lg" />
        </button>
      </div>
      {shown.map((post) => (
        <div key={post.id}>{renderCard(post)}</div>
      ))}
      {showingAll && all.phase === "error" && (
        <Alert tone="error">
          Couldn&apos;t load the other emergency posts.{" "}
          <Button variant="ghost" onClick={all.retry}>
            Try again
          </Button>
        </Alert>
      )}
      {!showingAll && count > pinned.length && (
        <Button variant="secondary" className="self-center" onClick={() => setShowingAll(true)}>
          <Icon name="expand_more" size="sm" className="text-outline" />
          Show all ({count})
        </Button>
      )}
      {showingAll && (all.phase === "loading" || all.hasMore) && (
        <Button
          variant="secondary"
          className="self-center"
          loading={all.phase === "loading" || all.loadingMore}
          onClick={all.loadMore}
        >
          {all.phase === "loading" || all.loadingMore ? "Loading…" : "Load more"}
        </Button>
      )}
    </section>
  );
}
