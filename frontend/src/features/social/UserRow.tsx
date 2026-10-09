import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import type { UserRowData } from "@/lib/api/types";
import { FollowButton } from "./FollowButton";

/**
 * One person in the followers and following lists (Stitch c3): avatar, name, handle, optional bio
 * and a Follow button (none on your own row). A blank display name shows `@username` once. The
 * trust metrics, tiers, "more" menu and shared-audit lines of c3 are not built.
 */
export function UserRow({
  user,
  onFollowChange,
}: {
  user: UserRowData;
  onFollowChange?: (following: boolean) => void;
}) {
  const hasName = user.display_name.trim() !== "";
  const name = hasName ? user.display_name : `@${user.username}`;
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
              {name}
            </span>
            {hasName && (
              <span className="truncate font-label-code text-label-badge text-outline">
                @{user.username}
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
          {user.bio}
        </p>
      )}
    </article>
  );
}
