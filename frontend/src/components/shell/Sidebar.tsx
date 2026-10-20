import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { buttonClasses } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Logo } from "@/components/ui/Logo";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { AccountMenu, type MenuAction } from "./AccountMenu";
import {
  footerItems,
  isActive,
  LOG_IN,
  NEW_POST,
  NEW_POST_BLOCKED_HINT,
  NOTIFICATIONS,
  nameOf,
  primaryItems,
  userMenuItems,
  type NavItem,
  type ShellUser,
} from "./nav-items";
import { ShellLink } from "./ShellLink";
import { UnreadBadge, unreadHint } from "./UnreadBadge";

export const USER_MENU_ID = "rz-user-menu";
export const NEW_POST_HINT_ID = "rz-new-post-hint-rail";

export interface SidebarProps {
  user: ShellUser | null;
  /** While the session is restored, the account area is a same-size placeholder. */
  loading?: boolean;
  pathname: string;
  /** Opens the composer (Part 4). Until then the button does nothing. */
  onNewPost?: () => void;
  /** Called instead when the email is unverified: the button is `aria-disabled`, not `disabled`. */
  onNewPostBlocked?: () => void;
  /** Log out, the last entry of the user menu. */
  actions?: MenuAction[];
  /** Unread notifications, shown on the Notifications link (Part 13). */
  unreadCount?: number;
}

/** Stitch b1 L20/L21 (main list) and L32/L33 (footer list): same shape, footer is smaller. */
function itemClasses(active: boolean, size: "main" | "footer"): string {
  return cn(
    "flex items-center justify-center gap-space-sm rounded-lg px-space-md transition-colors xl:justify-start",
    size === "main"
      ? "py-space-sm font-body-md text-body-md"
      : "py-space-xs font-body-sm text-body-sm",
    active
      ? "bg-secondary font-semibold text-on-secondary"
      : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
  );
}

function SidebarLink({
  item,
  pathname,
  size,
  badge = 0,
}: {
  item: NavItem;
  pathname: string;
  size: "main" | "footer";
  /** Unread count for this link (only Notifications has one). */
  badge?: number;
}) {
  const active = !item.external && isActive(pathname, item.href);
  return (
    <ShellLink
      item={item}
      active={active}
      title={item.label}
      label={badge > 0 ? `${item.label}${unreadHint(badge)}` : undefined}
      className={itemClasses(active, size)}
    >
      <span className="relative flex">
        <Icon name={item.icon} size="xl" />
        {/* The dock has no room for a pill: a number on the icon's corner. */}
        {badge > 0 && (
          <span className="xl:hidden">
            <UnreadBadge count={badge} variant="corner" inverted={active} />
          </span>
        )}
      </span>
      {/* Hidden in the icon dock, but still the link's name. */}
      <span className="sr-only xl:not-sr-only">{item.label}</span>
      {badge > 0 && (
        <span className="ml-auto hidden xl:flex">
          <UnreadBadge count={badge} variant="pill" inverted={active} />
        </span>
      )}
    </ShellLink>
  );
}

/**
 * The left rail (Stitch b1 L13–44): the full `w-64` rail at ≥1280px, a `w-16` icon dock at
 * 768–1279px, hidden on phones (MobileNav takes over).
 */
export function Sidebar({
  user,
  loading,
  pathname,
  onNewPost,
  onNewPostBlocked,
  actions,
  unreadCount = 0,
}: SidebarProps) {
  const footer = footerItems(user);
  const blocked = Boolean(user && !user.is_email_verified);

  return (
    <aside className="fixed top-0 left-0 z-50 hidden h-full w-16 flex-col justify-between border-r border-outline-variant/30 bg-surface-container-lowest md:flex xl:w-64">
      <div className="flex flex-col">
        <div className="flex h-16 items-center justify-center gap-space-sm border-b border-outline-variant/30 xl:justify-start xl:px-space-lg">
          <Link href="/home" className="rounded-lg">
            <span className="hidden xl:block">
              <Logo size="md" />
            </span>
            <span className="block xl:hidden">
              <Logo variant="mark" size="md" />
            </span>
          </Link>
        </div>
        <div className="flex flex-col gap-space-sm p-space-sm">
          <nav aria-label="Main" className="flex flex-col gap-space-xs">
            {primaryItems(user).map((item) => (
              <SidebarLink
                key={item.href}
                item={item}
                pathname={pathname}
                size="main"
                badge={item.href === NOTIFICATIONS.href ? unreadCount : 0}
              />
            ))}
          </nav>
          {user && (
            <div className="pt-space-sm">
              {/* aria-disabled keeps the button focusable, so a click can explain itself. */}
              <button
                type="button"
                title={NEW_POST.label}
                aria-disabled={blocked || undefined}
                aria-describedby={blocked ? NEW_POST_HINT_ID : undefined}
                onClick={blocked ? onNewPostBlocked : onNewPost}
                className={cn(
                  "flex w-full items-center justify-center gap-space-xs rounded-lg bg-secondary px-space-md py-space-sm font-body-md text-body-md font-semibold text-on-secondary shadow-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary/30 aria-disabled:cursor-not-allowed aria-disabled:opacity-60",
                  !blocked && "hover:bg-on-secondary-container",
                )}
              >
                <Icon name={NEW_POST.icon} size="lg" />
                <span className="sr-only xl:not-sr-only">{NEW_POST.label}</span>
              </button>
              {blocked && (
                <span id={NEW_POST_HINT_ID} className="sr-only">
                  {NEW_POST_BLOCKED_HINT}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col border-t border-outline-variant/30">
        {footer.length > 0 && (
          <div className="flex flex-col gap-space-xs px-space-sm py-space-xs">
            {footer.map((item) => (
              <SidebarLink key={item.href} item={item} pathname={pathname} size="footer" />
            ))}
          </div>
        )}
        {loading ? (
          <div
            data-testid="account-loading"
            className="flex items-center justify-center gap-space-sm border-t border-outline-variant/30 bg-surface-container-lowest p-space-sm xl:justify-start xl:p-space-md"
          >
            <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
            <div className="hidden min-w-0 flex-1 flex-col gap-space-xs xl:flex">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-3 w-16" />
            </div>
          </div>
        ) : user ? (
          <div className="flex items-center justify-center gap-space-sm border-t border-outline-variant/30 bg-surface-container-lowest p-space-sm xl:justify-between xl:p-space-md">
            <div className="hidden min-w-0 flex-1 items-center gap-space-sm xl:flex">
              <Avatar name={nameOf(user)} src={user.avatar_url} size={8} decorative />
              <div className="flex min-w-0 flex-col">
                <span className="truncate font-body-sm text-body-sm font-semibold text-on-surface">
                  {nameOf(user)}
                </span>
                <span className="truncate font-label-code text-label-code text-on-surface-variant">
                  @{user.username}
                </span>
              </div>
            </div>
            <button
              type="button"
              popoverTarget={USER_MENU_ID}
              aria-label="User menu"
              title="User menu"
              className="flex-shrink-0 rounded-lg p-space-xs text-outline transition-colors hover:bg-surface-container-low hover:text-on-surface"
            >
              <span className="block xl:hidden">
                <Avatar name={nameOf(user)} src={user.avatar_url} size={8} decorative />
              </span>
              <span className="hidden xl:block">
                <Icon name="more_horiz" size="xl" />
              </span>
            </button>
            <AccountMenu
              id={USER_MENU_ID}
              label="Account"
              items={userMenuItems(user)}
              actions={actions}
              placement="rail"
              pathname={pathname}
            />
          </div>
        ) : (
          <div className="flex flex-col gap-space-sm border-t border-outline-variant/30 p-space-sm xl:p-space-md">
            <Link
              href={LOG_IN.href}
              title={LOG_IN.label}
              className={buttonClasses({ variant: "secondary", className: "w-full" })}
            >
              <Icon name={LOG_IN.icon} size="lg" className="xl:hidden" />
              <span className="sr-only xl:not-sr-only">{LOG_IN.label}</span>
            </Link>
            <Link href="/signup" title="Sign up" className={buttonClasses({ className: "w-full" })}>
              <Icon name="person_add" size="lg" className="xl:hidden" />
              <span className="sr-only xl:not-sr-only">Sign up</span>
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}
