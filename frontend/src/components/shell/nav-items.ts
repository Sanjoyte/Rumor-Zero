/**
 * What the app shell links to, for each viewer (ARCHITECTURE §10). Visitors who aren't logged in
 * see only Home and Search, plus Log in / Sign up (user decision, 2026-10-01).
 */
import type { Me } from "@/lib/api/types";

/** The part of `/api/v1/me/` the shell shows. */
export type ShellUser = Pick<
  Me,
  "username" | "display_name" | "avatar_url" | "admin_url" | "is_email_verified"
>;

export interface NavItem {
  label: string;
  /** Material Symbols glyph (DESIGN.md › Iconography). */
  icon: string;
  href: string;
  /** Django Admin lives on the backend origin, so it opens in a new tab. */
  external?: boolean;
}

export const HOME: NavItem = { label: "Home", icon: "home", href: "/home" };
export const SEARCH: NavItem = { label: "Search", icon: "search", href: "/search" };
export const NOTIFICATIONS: NavItem = {
  label: "Notifications",
  icon: "notifications",
  href: "/notifications",
};
export const BOOKMARKS: NavItem = { label: "Bookmarks", icon: "bookmark", href: "/bookmarks" };
export const SETTINGS: NavItem = { label: "Settings", icon: "settings", href: "/settings" };
export const LOG_IN: NavItem = { label: "Log in", icon: "login", href: "/login" };

export const NEW_POST = { label: "New post", icon: "edit_note" } as const;
export const LOG_OUT = { label: "Log out", icon: "logout" } as const;

export function profileItem(user: ShellUser): NavItem {
  return { label: "Profile", icon: "person", href: `/u/${user.username}` };
}

/** "Moderation" only for staff, who get `admin_url` from `/api/v1/me/` (ARCHITECTURE §8). */
export function moderationItem(user: ShellUser | null): NavItem | null {
  if (!user?.admin_url) return null;
  return { label: "Moderation", icon: "fact_check", href: user.admin_url, external: true };
}

/** The rail's main list. New post follows it; the footer list holds the rest. */
export function primaryItems(user: ShellUser | null): NavItem[] {
  if (!user) return [HOME, SEARCH];
  return [HOME, SEARCH, NOTIFICATIONS, profileItem(user), BOOKMARKS];
}

export function footerItems(user: ShellUser | null): NavItem[] {
  if (!user) return [];
  const moderation = moderationItem(user);
  return moderation ? [moderation, SETTINGS] : [SETTINGS];
}

/** Phone account sheet: everything the five bottom tabs leave out. */
export function sheetItems(user: ShellUser): NavItem[] {
  const moderation = moderationItem(user);
  return moderation ? [BOOKMARKS, SETTINGS, moderation] : [BOOKMARKS, SETTINGS];
}

/** The rail's user-card menu. Log out follows these links (an action, not a page). */
export function userMenuItems(user: ShellUser): NavItem[] {
  return [profileItem(user), SETTINGS];
}

/** Active on the page itself and below it (`/u/ada/followers` keeps Profile active). */
export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Blank display names fall back to the handle (ARCHITECTURE §2). */
export function nameOf(user: ShellUser): string {
  return user.display_name.trim() || `@${user.username}`;
}
