/**
 * `rz_session=1` is a non-secret hint cookie the backend sets and clears together with the
 * httpOnly `rz_refresh` cookie (ARCHITECTURE §7). Without it there is nothing to refresh, so an
 * anonymous page load makes no auth request at all.
 */
export const SESSION_HINT_COOKIE = "rz_session";

export function hasSessionHint(
  cookies: string = typeof document === "undefined" ? "" : document.cookie,
): boolean {
  return cookies.split(";").some((pair) => pair.trim() === `${SESSION_HINT_COOKIE}=1`);
}
