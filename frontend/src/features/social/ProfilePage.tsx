"use client";

import Link from "next/link";
import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterChips } from "@/components/ui/FilterChips";
import { Skeleton } from "@/components/ui/Skeleton";
import type { UserProfile } from "@/lib/api/types";
import { SOCIAL_MESSAGES } from "./messages";
import { ProfileHeader } from "./ProfileHeader";
import { ProfilePosts } from "./ProfilePosts";
import type { PostFilter } from "./social-api";
import { useProfile } from "./useProfile";

export const PROFILE_CONTAINER =
  "mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg";

const CHIPS = [
  { id: "all", label: "All" },
  { id: "fact", label: "Facts" },
  { id: "opinion", label: "Opinions" },
];

/** A page for an account that doesn't exist or can't be loaded (profile, followers, following). */
export function ProfileProblem({
  phase,
  onRetry,
}: {
  phase: "not-found" | "error";
  onRetry: () => void;
}) {
  if (phase === "not-found") {
    return (
      <EmptyState
        icon="person_off"
        title="Profile not found"
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
        {SOCIAL_MESSAGES.profileNotFound}
      </EmptyState>
    );
  }
  return (
    <Alert tone="error" title="Couldn't load this profile">
      <p>{SOCIAL_MESSAGES.profileFailed}</p>
      <Button variant="secondary" onClick={onRetry} className="mt-space-md">
        Try again
      </Button>
    </Alert>
  );
}

/**
 * `/u/[username]` (Stitch c1): the header card and the person's posts with All / Facts / Opinions
 * chips. The header arrives server-rendered (`initial`, the anonymous view); a signed-in visitor
 * fetches once more for `is_following` and `is_me`.
 */
export function ProfilePage({
  username,
  initial,
}: {
  username: string;
  initial: UserProfile | null;
}) {
  const { profile, phase, viewerReady, retry, followed } = useProfile(username, initial);
  const [filter, setFilter] = useState<PostFilter>("all");

  if (phase === "loading") {
    return (
      <div aria-busy="true" className={PROFILE_CONTAINER}>
        <span className="sr-only">Loading profile…</span>
        <Skeleton className="h-56 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (!profile || phase === "not-found" || phase === "error") {
    return (
      <div className={PROFILE_CONTAINER}>
        <ProfileProblem phase={phase === "not-found" ? "not-found" : "error"} onRetry={retry} />
      </div>
    );
  }

  const name = profile.display_name.trim() || `@${profile.username}`;
  return (
    <div className={PROFILE_CONTAINER}>
      <ProfileHeader profile={profile} viewerReady={viewerReady} onFollowChange={followed} />
      <FilterChips
        label="Show"
        chips={CHIPS}
        selected={[filter]}
        onChange={(next) => setFilter((next[0] ?? "all") as PostFilter)}
      />
      <ProfilePosts
        key={`${profile.username}:${filter}`}
        username={profile.username}
        filter={filter}
        isMe={profile.is_me && viewerReady}
        name={name}
      />
    </div>
  );
}
