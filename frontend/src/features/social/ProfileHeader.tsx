import Link from "next/link";
import type { ReactNode } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { buttonClasses } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import type { UserProfile } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatCount, formatMonthYear } from "@/lib/format";
import { CredibilityBadge } from "@/features/reputation/CredibilityBadge";
import { FollowButton } from "./FollowButton";

function Counter({
  value,
  label,
  dot,
  href,
}: {
  value: number;
  label: string;
  dot?: "primary" | "error";
  href?: string;
}) {
  const body: ReactNode = (
    <>
      <span className="flex items-center gap-space-xs">
        {dot && (
          <span
            aria-hidden="true"
            className={cn("h-2 w-2 rounded-full", dot === "primary" ? "bg-primary" : "bg-error")}
          />
        )}
        <span className="font-label-metric text-label-metric text-on-surface">
          {formatCount(value)}
        </span>
      </span>
      <span className="mt-0.5 font-label-code text-label-badge tracking-wider text-on-surface-variant uppercase">
        {label}
      </span>
    </>
  );
  return href ? (
    <Link href={href} prefetch={false} className="flex flex-col rounded-lg hover:underline">
      {body}
    </Link>
  ) : (
    <div className="flex flex-col">{body}</div>
  );
}

/**
 * The profile card (Stitch c1): avatar, name, handle, Follow or Edit profile, bio, join date, post
 * count, the credibility score (Part 11B, in place of c1's trust score, neutral) and the counters.
 * A blank display name shows `@username` once. Not built: the seal, the "Author" badge,
 * affiliation, peer reviews, share and more buttons, and the side widgets (the Credibility widget
 * is 11D). `viewerReady` is false while a signed-in visitor's own view is still loading, so the
 * button never shows the wrong state.
 */
export function ProfileHeader({
  profile,
  viewerReady,
  onFollowChange,
}: {
  profile: UserProfile;
  viewerReady: boolean;
  onFollowChange: (following: boolean) => void;
}) {
  const hasName = profile.display_name.trim() !== "";
  const name = hasName ? profile.display_name : `@${profile.username}`;
  const base = `/u/${profile.username}`;
  const { counts } = profile;
  const posts = `${formatCount(counts.posts)} ${counts.posts === 1 ? "post" : "posts"}`;

  return (
    <Card as="section" aria-label="Profile" className="p-space-lg">
      <div className="flex flex-col items-start justify-between gap-space-md sm:flex-row">
        <div className="flex min-w-0 items-center gap-space-md">
          <Avatar name={name} src={profile.avatar_url} size={20} decorative className="shrink-0" />
          <div className="flex min-w-0 flex-col">
            <h1 className="font-headline-lg text-headline-lg tracking-tight break-words text-on-surface">
              {name}
            </h1>
            {hasName && (
              <span className="truncate font-label-code text-label-code font-semibold text-secondary">
                @{profile.username}
              </span>
            )}
          </div>
        </div>
        <div className="shrink-0 self-start sm:self-auto">
          {!viewerReady ? (
            <Skeleton className="h-10 w-24" />
          ) : profile.is_me ? (
            <Link
              href="/settings"
              prefetch={false}
              className={buttonClasses({ variant: "secondary" })}
            >
              <Icon name="edit" size="lg" />
              Edit profile
            </Link>
          ) : (
            <FollowButton
              username={profile.username}
              initialFollowing={profile.is_following}
              onChange={onFollowChange}
            />
          )}
        </div>
      </div>
      {profile.bio && (
        <p className="mt-space-md font-body-md text-body-md leading-relaxed break-words whitespace-pre-wrap text-on-surface/90">
          {profile.bio}
        </p>
      )}
      <p className="mt-space-md flex flex-wrap items-center gap-x-space-md gap-y-space-xs font-body-sm text-body-sm text-on-surface-variant">
        <span className="flex items-center gap-space-xs">
          <Icon name="calendar_today" size="lg" className="text-outline" />
          Joined {formatMonthYear(profile.created_at)}
        </span>
        <span aria-hidden="true" className="text-outline-variant">
          ·
        </span>
        <span>{posts}</span>
        <span aria-hidden="true" className="text-outline-variant">
          ·
        </span>
        <CredibilityBadge variant="header" reputation={profile.reputation} />
      </p>
      <div className="mt-space-md grid grid-cols-2 gap-space-sm rounded-lg border border-outline-variant/30 bg-surface-container-low p-space-md sm:grid-cols-4">
        <Counter value={counts.followers} label="Followers" href={`${base}/followers`} />
        <Counter value={counts.following} label="Following" href={`${base}/following`} />
        <Counter value={counts.verified} label="Verified" dot="primary" />
        <Counter value={counts.false} label="FALSE" dot="error" />
      </div>
    </Card>
  );
}
