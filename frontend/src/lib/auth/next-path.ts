/**
 * Where to go after logging in: the `?next=` value, but only if it stays on this site. Anything
 * that could leave the origin, or loop back into the auth pages or the API, gives null.
 */
// "/reset-password" and "/verify-email/" carry a single-use key in the path, so they never become a
// `next` target ("/verify-email" itself, the "check your inbox" page, is fine).
const BLOCKED_PREFIXES = ["/api/", "/login", "/signup", "/reset-password", "/verify-email/"];

/** A backslash (browsers read "/\evil.com" as "//evil.com") or a control character. */
function hasUnsafeCharacter(value: string): boolean {
  for (const char of value) {
    const code = char.charCodeAt(0);
    if (char === "\\" || code < 0x20 || code === 0x7f) return true;
  }
  return false;
}

function startsWithSegment(path: string, prefix: string): boolean {
  if (prefix.endsWith("/")) return path.startsWith(prefix);
  return path === prefix || path.startsWith(`${prefix}/`) || path.startsWith(`${prefix}?`);
}

export function safeNextPath(
  raw: string | null | undefined,
  origin: string = typeof window === "undefined" ? "http://localhost" : window.location.origin,
): string | null {
  if (!raw || !raw.startsWith("/") || hasUnsafeCharacter(raw)) return null;
  let url: URL;
  try {
    url = new URL(raw, origin);
  } catch {
    return null;
  }
  if (url.origin !== new URL(origin).origin) return null;
  // Dot segments are resolved by URL: "/.//evil.com" becomes "//evil.com".
  if (url.pathname.startsWith("//")) return null;
  const path = url.pathname;
  if (path === "/api" || BLOCKED_PREFIXES.some((prefix) => startsWithSegment(path, prefix))) {
    return null;
  }
  return `${path}${url.search}${url.hash}`;
}
