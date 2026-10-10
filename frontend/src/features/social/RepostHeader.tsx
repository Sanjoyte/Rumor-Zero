import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import type { UserSummary } from "@/lib/api/types";
import { cn } from "@/lib/cn";

/**
 * "Reposted by @x" above a reposted card (Part 7B; Stitch has no such line, so it borrows the
 * card's label style). The name links to the profile, above the card's stretched claim link.
 */
export function RepostHeader({ user, className }: { user: UserSummary; className?: string }) {
  const hasName = user.display_name.trim() !== "";
  const name = hasName ? user.display_name : `@${user.username}`;
  return (
    <p
      className={cn(
        "relative z-10 flex w-fit max-w-full items-center gap-space-xs font-label-code text-label-code text-outline",
        className,
      )}
    >
      <Icon name="cached" size="sm" />
      <span>Reposted by</span>
      <Link
        href={`/u/${user.username}`}
        prefetch={false}
        className="min-w-0 truncate font-semibold text-on-surface-variant hover:underline focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none"
      >
        {name}
      </Link>
    </p>
  );
}
