import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";
import { Logo } from "@/components/ui/Logo";
import { cn } from "@/lib/cn";
import { AccountMenu } from "./AccountMenu";
import {
  HOME,
  isActive,
  LOG_IN,
  NEW_POST,
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

export interface MobileNavProps {
  user: ShellUser | null;
  pathname: string;
  onNewPost?: () => void;
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
export function MobileNav({ user, pathname, onNewPost }: MobileNavProps) {
  return (
    <>
      <header className="fixed top-0 right-0 left-0 z-40 flex h-16 items-center justify-between border-b border-outline-variant/30 bg-surface-container-lowest px-margin-mobile md:hidden">
        <Link href={HOME.href} className="rounded-lg">
          <Logo size="sm" />
        </Link>
        {user ? (
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
        {user ? (
          <>
            <button
              type="button"
              onClick={onNewPost}
              className={cn(TAB, "text-secondary hover:text-on-secondary-container")}
            >
              <Icon name={NEW_POST.icon} size="2xl" />
              <span>{NEW_POST.label}</span>
            </button>
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
