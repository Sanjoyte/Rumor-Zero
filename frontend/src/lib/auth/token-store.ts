/**
 * The access token lives here, in memory only (ARCHITECTURE §7, guide §4.6): never in
 * localStorage, sessionStorage or a script-readable cookie. A reload loses it, and Part 1's refresh
 * call gets a new one from the httpOnly refresh cookie.
 *
 * On the server this module is shared by every request, so writes are ignored there and reads
 * return null: one visitor's token can never leak into another's render.
 */
let accessToken: string | null = null;
const listeners = new Set<() => void>();

function inBrowser(): boolean {
  return typeof window !== "undefined";
}

export function getAccessToken(): string | null {
  return inBrowser() ? accessToken : null;
}

export function setAccessToken(token: string | null): void {
  if (!inBrowser()) return;
  accessToken = token;
  for (const listener of listeners) listener();
}

export function subscribeToAccessToken(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
