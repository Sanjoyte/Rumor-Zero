/**
 * The server render of `/p/[id]` reads the post straight from Django (ARCHITECTURE §1, ANALYSIS d):
 * server to server, anonymous, uncached. No relay and no secret: the backend only uses the shared
 * secret to decide whether to trust a forwarded client IP, and an anonymous read needs neither.
 * Waiting on `fetch` costs no Worker CPU, but a sleeping Render dyno takes about a minute, so the
 * wait is short and a failure falls back to the client fetching the post itself.
 */
import { parseBackendOrigin } from "./backend-origin";
import type { Post } from "./types";

export const SSR_FETCH_TIMEOUT_MS = 5_000;

export type PublicPostResult =
  | { kind: "found"; post: Post }
  | { kind: "not-found" }
  /** Backend down, slow, misconfigured or odd: not a 404, so the page lets the client try. */
  | { kind: "unavailable" };

export type PublicPostOptions = {
  backendOrigin?: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
};

function looksLikePost(value: unknown): value is Post {
  if (typeof value !== "object" || value === null) return false;
  const post = value as Record<string, unknown>;
  return (
    typeof post.id === "string" &&
    typeof post.content === "string" &&
    typeof post.status === "string" &&
    typeof post.post_type === "string" &&
    typeof post.author === "object" &&
    post.author !== null &&
    Array.isArray(post.sources)
  );
}

/** The post as an anonymous visitor sees it (a removed post arrives as its tombstone). */
export async function fetchPublicPost(
  id: string,
  options: PublicPostOptions = {},
): Promise<PublicPostResult> {
  const origin = parseBackendOrigin(options.backendOrigin ?? process.env.BACKEND_ORIGIN);
  if (!origin) return { kind: "unavailable" };
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  try {
    const response = await fetchImpl(`${origin}/api/v1/posts/${encodeURIComponent(id)}/`, {
      cache: "no-store",
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(options.timeoutMs ?? SSR_FETCH_TIMEOUT_MS),
    });
    if (response.status === 404) return { kind: "not-found" };
    if (!response.ok) return { kind: "unavailable" };
    const body: unknown = await response.json();
    return looksLikePost(body) ? { kind: "found", post: body } : { kind: "unavailable" };
  } catch {
    return { kind: "unavailable" };
  }
}
