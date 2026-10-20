"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon } from "@/components/ui/Icon";
import { LoadMore } from "@/components/ui/LoadMore";
import { Skeleton } from "@/components/ui/Skeleton";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { useCursorFeed } from "@/features/posts/useCursorFeed";
import type { UserRowData } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { listErrorMessage, SOCIAL_MESSAGES } from "./messages";
import { PROFILE_CONTAINER, ProfileProblem } from "./ProfilePage";
import { fetchConnections, type ConnectionKind } from "./social-api";
import { UserRow } from "./UserRow";
import { useProfile } from "./useProfile";

const PREFIX = "connections";
const userKey = (user: UserRowData) => user.id;

export function RowSkeleton() {
  return (
    <div className="flex items-center gap-space-sm p-space-md">
      <Skeleton className="h-10 w-10 rounded-full" />
      <div className="flex flex-1 flex-col gap-space-xs">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  );
}

/**
 * `/u/[username]/followers` and `/following` (Stitch c3): a back link, the two tabs with their
 * counts (each tab is its own address), and the people newest follow first. Not built from c3: the
 * network header card, category chips, the in-list filter, trust metrics, tiers and the directory
 * banner. The page is client-rendered (no server read), so it costs no extra Worker work.
 */
export function Connections({ username, tab }: { username: string; tab: ConnectionKind }) {
  const router = useRouter();
  const { status, user } = useAuth();
  const { profile, phase, retry } = useProfile(username, null);
  const feed = useCursorFeed({
    fetchPage: (cursor, signal) => fetchConnections(username, tab, cursor, signal),
    keyOf: userKey,
    enabled: status !== "loading",
    resetKey: user?.id ?? null,
  });

  if (phase === "not-found" || phase === "error") {
    return (
      <div className={PROFILE_CONTAINER}>
        <ProfileProblem phase={phase} onRetry={retry} />
      </div>
    );
  }

  const name = profile ? profile.display_name.trim() || `@${profile.username}` : null;
  const counts = profile?.counts;
  const tabs = [
    { id: "followers", label: "Followers", count: counts?.followers },
    { id: "following", label: "Following", count: counts?.following },
  ];
  const emptyText =
    tab === "followers"
      ? { title: "No followers yet", body: `Nobody follows ${name ?? "this account"} yet.` }
      : {
          title: "Not following anyone yet",
          body: `${name ?? "This account"} doesn't follow anyone yet.`,
        };

  return (
    <div className={PROFILE_CONTAINER}>
      <h1 className="sr-only">
        {tab === "followers" ? "People following" : "People followed by"} {name ?? username}
      </h1>
      <Link
        href={`/u/${username}`}
        prefetch={false}
        className="inline-flex items-center gap-space-xs self-start font-body-sm text-body-sm font-semibold text-secondary hover:text-on-secondary-container hover:underline"
      >
        <Icon name="arrow_back" size="md" />
        Back to {name ? `${name} (@${username})` : `@${username}`}
      </Link>
      <Tabs
        tabs={tabs}
        value={tab}
        onChange={(id) => {
          if (id !== tab) router.push(`/u/${username}/${id}`);
        }}
        label="People"
        idPrefix={PREFIX}
      />
      <TabPanel idPrefix={PREFIX} tab={tab} selected>
        {feed.phase === "idle" || feed.phase === "loading" ? (
          <div
            aria-busy="true"
            className="divide-y divide-outline-variant/30 rounded-lg border border-outline-variant/30 bg-surface-container-lowest"
          >
            <span className="sr-only">Loading people…</span>
            <RowSkeleton />
            <RowSkeleton />
            <RowSkeleton />
          </div>
        ) : feed.phase === "error" ? (
          <Alert tone="error" title="Couldn't load this list">
            <p>{listErrorMessage(feed.error)}</p>
            <Button variant="secondary" onClick={feed.retry} className="mt-space-md">
              Try again
            </Button>
          </Alert>
        ) : feed.items.length === 0 ? (
          <EmptyState icon="group" title={emptyText.title}>
            {emptyText.body}
          </EmptyState>
        ) : (
          <>
            <div className="divide-y divide-outline-variant/30 overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-lowest">
              {feed.items.map((row) => (
                <UserRow key={row.id} user={row} />
              ))}
            </div>
            {feed.moreError !== null && (
              <Alert tone="error" className="mt-space-md">
                {SOCIAL_MESSAGES.moreFailed} Try again.
              </Alert>
            )}
            <LoadMore
              hasMore={feed.hasMore}
              loading={feed.loadingMore}
              onClick={feed.loadMore}
              endLabel="That's everyone."
            />
          </>
        )}
      </TabPanel>
    </div>
  );
}
