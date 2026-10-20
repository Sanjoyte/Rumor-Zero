import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { CredibilityBadge } from "@/features/reputation/CredibilityBadge";
import { Highlight } from "@/features/search/Highlight";
import type { UserRowData } from "@/lib/api/types";
import { FollowButton } from "./FollowButton";

/**
 * One person in the followers and following lists (Stitch c3): avatar, name, handle, optional bio,
 * the credibility chip with the verified count (Part 11B: c3's trust metric, neutral) and a Follow
 * button (none on your own row). A blank display name shows `@username` once. The chip sits on its
 * own line outside the profile link, so the link's name stays the person's name. The tiers, "more"
 * menu and shared-audit lines of c3 are not built.
 */
export function UserRow({
  user,
  onFollowChange,
  highlight,
}: {
  user: UserRowData;
  onFollowChange?: (following: boolean) => void;
  /** Search terms to mark in the name, handle and bio (Part 12, `queryTerms`). */
  highlight?: string[];
}) {
  const hasName = user.display_name.trim() !== "";
  const name = hasName ? user.display_name : `@${user.username}`;
  const mark = (text: string) =>
    highlight?.length ? <Highlight text={text} terms={highlight} /> : text;
  return (
    <article className="p-space-md transition-colors hover:bg-surface-container-low/50">
      <div className="flex items-start justify-between gap-space-md">
        <Link
          href={`/u/${user.username}`}
          prefetch={false}
          className="group flex min-w-0 gap-space-sm focus-visible:outline-none"
        >
          <Avatar name={name} src={user.avatar_url} size={10} decorative />
          <span className="flex min-w-0 flex-col justify-center">
            <span className="truncate font-body-md text-body-md font-bold text-on-surface group-hover:underline">
              {mark(name)}
            </span>
            {hasName && (
              <span className="truncate font-label-code text-label-badge text-outline">
                @{mark(user.username)}
              </span>
            )}
          </span>
        </Link>
        {!user.is_me && (
          <FollowButton
            username={user.username}
            initialFollowing={user.is_following}
            onChange={onFollowChange}
            className="shrink-0"
          />
        )}
      </div>
      {user.bio && (
        <p className="mt-space-sm pl-12 font-body-sm text-body-sm break-words whitespace-pre-wrap text-on-surface-variant">
          {mark(user.bio)}
        </p>
      )}
      <div className="mt-space-xs pl-12">
        <CredibilityBadge
          variant="row"
          reputation={user.reputation}
          verified={user.counts.verified}
        />
      </div>
    </article>
  );
}
