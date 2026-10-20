"use client";

import { useMemo } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadMore } from "@/components/ui/LoadMore";
import { useCursorFeed } from "@/features/posts/useCursorFeed";
import { listErrorMessage } from "@/features/social/messages";
import { RowSkeleton } from "@/features/social/Connections";
import { UserRow } from "@/features/social/UserRow";
import type { UserRowData } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { queryTerms } from "./highlight";
import { SEARCH_MESSAGES, SEARCH_RESULT_CAP } from "./messages";
import { searchPeople } from "./search-api";

const userKey = (user: UserRowData) => user.id;
const LIST =
  "divide-y divide-outline-variant/30 overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-lowest";

/**
 * The people for one query: exact username first, then username prefix, then display-name words,
 * A to Z inside each (never by credibility). Mount it with a `key` that includes the query. Rows
 * are the follower rows, so each has the credibility chip and a Follow button.
 */
export function PeopleResults({ q }: { q: string }) {
  const { status, user } = useAuth();
  const feed = useCursorFeed({
    fetchPage: (cursor, signal) => searchPeople(q, cursor, signal),
    keyOf: userKey,
    enabled: status !== "loading",
    resetKey: user?.id ?? null,
  });
  const terms = useMemo(() => queryTerms(q), [q]);

  if (feed.phase === "idle" || feed.phase === "loading") {
    return (
      <div aria-busy="true" className={LIST}>
        <span className="sr-only">Loading people…</span>
        <RowSkeleton />
        <RowSkeleton />
        <RowSkeleton />
      </div>
    );
  }
  if (feed.phase === "error") {
    return (
      <Alert tone="error" title="Couldn't load people">
        <p>{listErrorMessage(feed.error)}</p>
        <Button variant="secondary" onClick={feed.retry} className="mt-space-md">
          Try again
        </Button>
      </Alert>
    );
  }
  if (feed.items.length === 0) {
    return (
      <EmptyState icon="group" title={SEARCH_MESSAGES.noPeopleTitle(q)}>
        {SEARCH_MESSAGES.noPeopleBody}
      </EmptyState>
    );
  }
  const capped = feed.items.length >= SEARCH_RESULT_CAP;
  return (
    <>
      <div className={LIST}>
        {feed.items.map((row) => (
          <UserRow key={row.id} user={row} highlight={terms} />
        ))}
      </div>
      {feed.moreError !== null && (
        <Alert tone="error" className="mt-space-md">
          {SEARCH_MESSAGES.morePeopleFailed} Try again.
        </Alert>
      )}
      <LoadMore
        hasMore={feed.hasMore}
        loading={feed.loadingMore}
        onClick={feed.loadMore}
        endLabel={capped ? SEARCH_MESSAGES.capped : SEARCH_MESSAGES.everyone}
      />
    </>
  );
}
