import Form from "next/form";
import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";
import { LOG_IN, nameOf, profileItem, SEARCH, type ShellUser } from "./nav-items";

export interface TopBarProps {
  user: ShellUser | null;
}

/**
 * The fixed top bar from 768px up (Stitch b1 L50–57): a search box that opens `/search?q=…`, and
 * the account avatar (or Log in). Stitch's "Verification Ledger" pill is not built (ANALYSIS b-3).
 * The search box keeps b1's compact classes rather than the 44px TextField.
 */
export function TopBar({ user }: TopBarProps) {
  return (
    <header className="fixed top-0 right-0 left-16 z-40 hidden h-16 items-center justify-between gap-space-lg border-b border-outline-variant/30 bg-surface-container-lowest px-space-lg md:flex xl:left-64">
      <Form action={SEARCH.href} role="search" className="relative max-w-xl flex-1">
        <label htmlFor="rz-top-search" className="sr-only">
          Search
        </label>
        <Icon
          name="search"
          size="xl"
          className="pointer-events-none absolute top-1/2 left-space-md -translate-y-1/2 text-outline"
        />
        <input
          id="rz-top-search"
          name="q"
          type="search"
          placeholder="Search posts and people"
          className="w-full appearance-none rounded-lg border border-outline-variant/30 bg-surface-container-low py-space-xs pr-space-md pl-10 font-body-sm text-body-sm text-on-surface placeholder:text-outline focus:border-secondary focus:ring-0 focus:outline-none"
        />
      </Form>
      <div className="flex items-center gap-space-md">
        {user ? (
          <Link
            href={profileItem(user).href}
            aria-label="Your profile"
            title="Your profile"
            className="flex-shrink-0 rounded-full transition-opacity hover:opacity-90"
          >
            <Avatar name={nameOf(user)} src={user.avatar_url} size={8} decorative />
          </Link>
        ) : (
          <Link
            href={LOG_IN.href}
            className="font-body-md text-body-md font-medium whitespace-nowrap text-secondary transition-colors hover:text-on-secondary-container hover:underline"
          >
            {LOG_IN.label}
          </Link>
        )}
      </div>
    </header>
  );
}
