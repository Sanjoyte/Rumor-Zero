import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";
import { Logo } from "@/components/ui/Logo";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { AccountMenu, type MenuAction } from "./AccountMenu";
import {
  HOME,
  isActive,
  LOG_IN,
  NEW_POST,
  NEW_POST_BLOCKED_HINT,
  NOTIFICATIONS,
  nameOf,
  profileItem,
  SEARCH,
  sheetItems,
  type NavItem,
  type ShellUser,
} from "./nav-items";
import { ShellLink } from "./ShellLink";

export const ACCOUNT_SHEET_ID = "rz-account-sheet";
export const NEW_POST_HINT_ID = "rz-new-post-hint-tab";

export interface MobileNavProps {
  user: ShellUser | null;
  loading?: boolean;
  pathname: string;
  onNewPost?: () => void;
  /** Called instead when the email is unverified: the tab is `aria-disabled`, not `disabled`. */
  onNewPostBlocked?: () => void;
  /** Log out, the last entry of the account sheet. */
  actions?: MenuAction[];
}

const TAB =
  "flex flex-1 flex-col items-center justify-center gap-0.5 font-label-badge text-label-badge transition-colors";

function Tab({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = isActive(pathname, item.href);
  return (
    <ShellLink
      item={item}
      active={active}
      className={cn(
        TAB,
        active ? "text-secondary" : "text-on-surface-variant hover:text-on-surface",
      )}
    >
      <Icon name={item.icon} size="2xl" filled={active} />
      <span>{item.label}</span>
    </ShellLink>
  );
}

/**
 * Phones (<768px; DESIGN.md "intended behavior"): a top bar with the logo and the account sheet,
 * and a bottom bar with five tabs (user decision, 2026-10-01). Logged out: Home, Search, Log in.
 */
export function MobileNav({
  user,
  loading,
  pathname,
  onNewPost,
  onNewPostBlocked,
  actions,
}: MobileNavProps) {
  const blocked = Boolean(user && !user.is_email_verified);
  return (
    <>
      <header className="fixed top-0 right-0 left-0 z-40 flex h-16 items-center justify-between border-b border-outline-variant/30 bg-surface-container-lowest px-margin-mobile md:hidden">
        <Link href={HOME.href} className="rounded-lg">
          <Logo size="sm" />
        </Link>
        {loading ? (
          <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
        ) : user ? (
          <>
            <button
              type="button"
              popoverTarget={ACCOUNT_SHEET_ID}
              aria-label="Account menu"
              title="Account menu"
              className="flex-shrink-0 rounded-full transition-opacity hover:opacity-90"
            >
              <Avatar name={nameOf(user)} src={user.avatar_url} size={8} decorative />
            </button>
            <AccountMenu
              id={ACCOUNT_SHEET_ID}
              label="Account"
              items={sheetItems(user)}
              actions={actions}
              placement="sheet"
              pathname={pathname}
            />
          </>
        ) : (
          <Link
            href={LOG_IN.href}
            className="font-body-md text-body-md font-medium text-secondary hover:text-on-secondary-container hover:underline"
          >
            {LOG_IN.label}
          </Link>
        )}
      </header>

      <nav
        aria-label="Main"
        className="fixed right-0 bottom-0 left-0 z-40 flex h-16 border-t border-outline-variant/30 bg-surface-container-lowest md:hidden"
      >
        <Tab item={HOME} pathname={pathname} />
        <Tab item={SEARCH} pathname={pathname} />
        {loading ? (
          <div className={TAB}>
            <Skeleton className="h-6 w-6 rounded-full" />
            <Skeleton className="h-3 w-10" />
          </div>
        ) : user ? (
          <>
            <button
              type="button"
              aria-disabled={blocked || undefined}
              aria-describedby={blocked ? NEW_POST_HINT_ID : undefined}
              onClick={blocked ? onNewPostBlocked : onNewPost}
              className={cn(
                TAB,
                "text-secondary aria-disabled:cursor-not-allowed aria-disabled:opacity-60",
                !blocked && "hover:text-on-secondary-container",
              )}
            >
              <Icon name={NEW_POST.icon} size="2xl" />
              <span>{NEW_POST.label}</span>
            </button>
            {/* Outside the button, so it describes it without becoming part of its name. */}
            {blocked && (
              <span id={NEW_POST_HINT_ID} className="sr-only">
                {NEW_POST_BLOCKED_HINT}
              </span>
            )}
            <Tab item={NOTIFICATIONS} pathname={pathname} />
            <Tab item={profileItem(user)} pathname={pathname} />
          </>
        ) : (
          <Tab item={LOG_IN} pathname={pathname} />
        )}
      </nav>
    </>
  );
}
