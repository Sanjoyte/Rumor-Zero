/**
 * The one rule for what BACKEND_ORIGIN may be, shared by the API relay and the server render of
 * `/p/[id]` (ARCHITECTURE §1). Plain module: it reads no environment and holds no secret.
 */

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/**
 * `value` as an origin (`https://host`), or null when it isn't one we may talk to: not a URL, has a
 * path, query, fragment or credentials, or is plain http to anything but this machine (the relay
 * sends a shared secret, so it may only travel in clear to loopback).
 */
export function parseBackendOrigin(value: string | undefined): string | null {
  let url: URL;
  try {
    url = new URL(value ?? "");
  } catch {
    return null;
  }
  const plainOrigin = url.pathname === "/" && !url.search && !url.hash && !url.username;
  const safeScheme =
    url.protocol === "https:" || (url.protocol === "http:" && LOOPBACK_HOSTS.has(url.hostname));
  return plainOrigin && safeScheme ? url.origin : null;
}
