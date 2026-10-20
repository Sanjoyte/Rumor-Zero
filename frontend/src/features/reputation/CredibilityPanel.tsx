"use client";

import Link from "next/link";
import { useState } from "react";
import { MeterBar } from "@/components/ui/charts/MeterBar";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon } from "@/components/ui/Icon";
import { LoadMore } from "@/components/ui/LoadMore";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCursorFeed } from "@/features/posts/useCursorFeed";
import type { LedgerEntry } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { cn } from "@/lib/cn";
import { formatDate, formatWeight } from "@/lib/format";
import { APPEAL_STATE_WORDS, CREDIBILITY_COPY } from "./ledger-copy";
import { fetchMyReputationEvents } from "./reputation-api";

const START_SCORE = 50;
const keyOf = (entry: LedgerEntry) => entry.id;

function Appeal({ entry }: { entry: LedgerEntry }) {
  const { appeal, post_id: postId } = entry;
  if (!appeal) return null;
  if (appeal.can_appeal && postId) {
    return (
      <Link
        href={`/p/${postId}`}
        prefetch={false}
        className="font-body-sm text-body-sm font-medium text-secondary hover:underline"
      >
        {CREDIBILITY_COPY.askAgain}
      </Link>
    );
  }
  if (appeal.status) {
    return (
      <span className="font-body-sm text-body-sm text-on-surface-variant">
        {APPEAL_STATE_WORDS[appeal.status]}
      </span>
    );
  }
  return null;
}

/** One row of your ledger. A reversed row is struck through and says so in a word. */
export function LedgerRow({ entry }: { entry: LedgerEntry }) {
  return (
    <li className="flex flex-col gap-space-xs border-t border-outline-variant/30 py-space-md first:border-t-0 sm:flex-row sm:items-start sm:justify-between sm:gap-space-lg">
      <div className="flex min-w-0 flex-col gap-space-xs">
        <p className="flex flex-wrap items-center gap-x-space-sm gap-y-space-xs">
          <span
            className={cn(
              "font-body-md text-body-md break-words text-on-surface",
              entry.reversed && "line-through",
            )}
          >
            {entry.label}
          </span>
          {entry.reversed && (
            <span className="rounded-lg border border-outline-variant/30 bg-surface-container px-space-xs py-0.5 font-label-badge text-label-badge text-on-surface-variant">
              {CREDIBILITY_COPY.reversed}
            </span>
          )}
        </p>
        <p className="flex flex-wrap items-center gap-x-space-sm gap-y-space-xs font-label-code text-label-badge text-outline">
          <time dateTime={entry.created_at}>{formatDate(entry.created_at)}</time>
          {entry.post_id && (
            <Link
              href={`/p/${entry.post_id}`}
              prefetch={false}
              className="text-secondary hover:underline"
            >
              {CREDIBILITY_COPY.viewPost}
            </Link>
          )}
        </p>
        <Appeal entry={entry} />
      </div>
      <p className="flex shrink-0 items-baseline gap-space-sm sm:flex-col sm:items-end sm:gap-space-xs">
        <span className="font-label-metric text-label-metric text-on-surface">
          {formatWeight(entry.positive, entry.negative)}
        </span>
        <span className="font-label-code text-label-badge text-outline">
          score after {entry.score_after}
        </span>
      </p>
    </li>
  );
}

export interface CredibilityPanelViewProps {
  phase: "loading" | "error" | "ready";
  entries: LedgerEntry[];
  hasMore: boolean;
  loadingMore: boolean;
  moreError: boolean;
  /** What the public sees (null = "New"); decides whether to say so. */
  publicScore: number | null;
  open: boolean;
  onToggle: () => void;
  onRetry: () => void;
  onLoadMore: () => void;
}

/** The panel, presentational (the dev gallery renders it without a session). */
export function CredibilityPanelView({
  phase,
  entries,
  hasMore,
  loadingMore,
  moreError,
  publicScore,
  open,
  onToggle,
  onRetry,
  onLoadMore,
}: CredibilityPanelViewProps) {
  const score = entries[0]?.score_after ?? START_SCORE;
  const count = `${entries.length}${hasMore ? "+" : ""}`;
  return (
    <Card as="section" aria-labelledby="credibility-panel-heading" className="p-space-lg">
      <div className="flex flex-col gap-space-md">
        <h2
          id="credibility-panel-heading"
          className="font-headline-sm text-headline-sm text-on-surface"
        >
          {CREDIBILITY_COPY.panelHeading}
        </h2>
        {phase === "error" ? (
          <Alert tone="error" title="Couldn't load your credibility">
            <p>{CREDIBILITY_COPY.loadFailed}</p>
            <Button variant="secondary" onClick={onRetry} className="mt-space-md">
              Try again
            </Button>
          </Alert>
        ) : phase === "loading" ? (
          <div aria-busy="true" className="flex flex-col gap-space-sm">
            <span className="sr-only">Loading your credibility…</span>
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-full" />
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-space-xs">
              <p className="font-label-metric text-label-metric text-on-surface">
                Your score: {score}
              </p>
              <MeterBar
                value={score}
                tone="neutral"
                summary={`Your credibility score is ${score} out of 100.`}
                table={{ caption: "Your credibility score", rows: [["Score", String(score)]] }}
              />
              {publicScore === null && (
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  {CREDIBILITY_COPY.hiddenNote}
                </p>
              )}
            </div>
            {entries.length === 0 ? (
              <EmptyState icon="history" title={CREDIBILITY_COPY.emptyTitle}>
                {CREDIBILITY_COPY.empty}
              </EmptyState>
            ) : (
              <div className="flex flex-col gap-space-sm">
                <Button
                  variant="ghost"
                  aria-expanded={open}
                  aria-controls="credibility-history"
                  onClick={onToggle}
                  className="self-start"
                >
                  <Icon name={open ? "expand_less" : "expand_more"} size="lg" />
                  {open ? "Hide history" : "Show history"} ({count})
                </Button>
                {open && (
                  <div id="credibility-history">
                    <ol className="flex flex-col">
                      {entries.map((entry) => (
                        <LedgerRow key={entry.id} entry={entry} />
                      ))}
                    </ol>
                    {moreError && (
                      <Alert tone="error">
                        <p>{CREDIBILITY_COPY.loadFailed}</p>
                      </Alert>
                    )}
                    <LoadMore
                      hasMore={hasMore}
                      loading={loadingMore}
                      onClick={onLoadMore}
                      endLabel={CREDIBILITY_COPY.end}
                      className="pb-space-md"
                    />
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  );
}

/**
 * Your credibility: the real score as a bar and your whole ledger behind a disclosure (Stitch c2's
 * "Credibility Index", re-purposed). Yours only: it reads `GET /me/reputation/events/`. While the
 * public score is hidden it says what others see. Neutral grey, like the widget. Part 14 mounts the
 * same component in Settings with `defaultOpen`.
 */
export function CredibilityPanel({
  publicScore,
  defaultOpen = false,
}: {
  publicScore: number | null;
  defaultOpen?: boolean;
}) {
  const { status, user } = useAuth();
  const [open, setOpen] = useState(defaultOpen);
  const feed = useCursorFeed({
    fetchPage: fetchMyReputationEvents,
    keyOf,
    enabled: status === "authenticated",
    resetKey: user?.id ?? null,
  });
  return (
    <CredibilityPanelView
      phase={feed.phase === "error" ? "error" : feed.phase === "ready" ? "ready" : "loading"}
      entries={feed.items}
      hasMore={feed.hasMore}
      loadingMore={feed.loadingMore}
      moreError={feed.moreError !== null}
      publicScore={publicScore}
      open={open}
      onToggle={() => setOpen((prev) => !prev)}
      onRetry={feed.retry}
      onLoadMore={feed.loadMore}
    />
  );
}
