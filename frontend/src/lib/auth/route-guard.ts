/**
 * App pages that need a logged-in user (ARCHITECTURE §10). Everything else in the app shell is
 * public: `/home`, `/search` and profiles work logged out.
 */
export const PROTECTED_PREFIXES = ["/notifications", "/bookmarks", "/settings"] as const;

export function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

/** `/login?next=<the page you wanted>`. */
export function loginRedirectFor(pathAndQuery: string): string {
  return `/login?next=${encodeURIComponent(pathAndQuery)}`;
}
