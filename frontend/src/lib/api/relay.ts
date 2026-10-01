/**
 * The API relay (ARCHITECTURE §1, ANALYSIS d): the browser only talks to the frontend origin, and
 * `src/app/api/[...path]/route.ts` forwards every `/api/*` request to Django at BACKEND_ORIGIN.
 *
 * Server-only. Never import this from a client component: it reads PROXY_SHARED_SECRET.
 */

/** Render's free tier takes about a minute to wake up. */
export const RELAY_TIMEOUT_MS = 70_000;

/** Request bodies are buffered (Django can't read chunked bodies). Covers 14B's 5 MB photos. */
export const MAX_BODY_BYTES = 6 * 1024 * 1024;

/** Browser headers that reach Django. Everything else (Host, hop-by-hop, X-RZ-*) is dropped. */
export const REQUEST_HEADER_ALLOWLIST = [
  "accept",
  "authorization",
  "content-type",
  "cookie",
  "origin",
  "x-requested-with",
  "if-none-match",
  "if-modified-since",
  "user-agent",
] as const;

/** Django response headers that reach the browser, besides Set-Cookie, Content-Length and Location. */
export const RESPONSE_HEADER_ALLOWLIST = [
  "content-type",
  "cache-control",
  "etag",
  "last-modified",
  "content-disposition",
  "x-content-type-options",
  "content-security-policy",
  "retry-after",
] as const;

const NULL_BODY_STATUSES = new Set([204, 205, 304]);
const GATEWAY_STATUSES = new Set([502, 503, 504]);
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);
/** A plausible IPv4/IPv6 literal. Django re-parses it strictly; this only keeps junk out. */
const IP_LITERAL = /^[0-9A-Fa-f:.]{2,45}$/;
/** Encoded "/", "\" and NUL would be decoded by Django into a different path than we checked. */
const ENCODED_SEPARATORS = /%(?:2f|5c|00)/i;

export type RelayEnv = {
  BACKEND_ORIGIN?: string;
  PROXY_SHARED_SECRET?: string;
};

export type RelayOptions = {
  timeoutMs?: number;
  maxBodyBytes?: number;
  readEnv?: () => RelayEnv;
  /** Looked up on every request, so test doubles and Next's patched fetch are both honoured. */
  getFetch?: () => typeof fetch;
};

type RelayConfig = { origin: string; secret: string };

function json(status: number, body: object, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store", ...headers },
  });
}

/** 503 for every "the backend didn't answer" case, so the client sees one shape (ARCHITECTURE §9). */
export function backendWaking(): Response {
  return json(
    503,
    { detail: "The server is waking up. Try again in a minute.", code: "backend_waking" },
    { "retry-after": "30" },
  );
}

/**
 * The backend origin and secret, or the name of the variable that is wrong. The value itself is
 * never returned or logged.
 */
export function readConfig(env: RelayEnv): RelayConfig | { invalid: string } {
  let url: URL;
  try {
    url = new URL(env.BACKEND_ORIGIN ?? "");
  } catch {
    return { invalid: "BACKEND_ORIGIN" };
  }
  const plainOrigin = url.pathname === "/" && !url.search && !url.hash && !url.username;
  // The relay adds the shared secret, so it may only travel in clear to this machine.
  const safeScheme =
    url.protocol === "https:" || (url.protocol === "http:" && LOOPBACK_HOSTS.has(url.hostname));
  if (!plainOrigin || !safeScheme) return { invalid: "BACKEND_ORIGIN" };
  const secret = env.PROXY_SHARED_SECRET ?? "";
  if (!secret) return { invalid: "PROXY_SHARED_SECRET" };
  return { origin: url.origin, secret };
}

/**
 * Maps the incoming URL to the backend. Returns an HTTP status instead when the path must not be
 * forwarded. Next has already resolved "..", "%2e%2e" and "\" in `request.url`; the origin and
 * prefix checks still run on the parsed target.
 */
export function buildTarget(requestUrl: string, origin: string): URL | 400 | 404 {
  const incoming = new URL(requestUrl);
  if (ENCODED_SEPARATORS.test(incoming.pathname)) return 400;
  const target = new URL(origin + incoming.pathname + incoming.search);
  if (target.origin !== origin || !target.pathname.startsWith("/api/")) return 404;
  return target;
}

/**
 * The visitor's IP: Cloudflare's `cf-connecting-ip` (set at the edge, can't be spoofed), else the
 * right-most `x-forwarded-for` entry. Locally `next dev` keeps a client-sent X-Forwarded-For
 * (`??=`), so only local dev can be spoofed.
 */
export function clientIp(headers: Headers): string | null {
  const cf = headers.get("cf-connecting-ip")?.trim();
  if (cf && IP_LITERAL.test(cf)) return cf;
  const last = headers.get("x-forwarded-for")?.split(",").at(-1)?.trim();
  if (last && IP_LITERAL.test(last)) return last;
  return null;
}

export function forwardRequestHeaders(
  incoming: Headers,
  secret: string,
  ip: string | null,
): Headers {
  const out = new Headers();
  for (const name of REQUEST_HEADER_ALLOWLIST) {
    const value = incoming.get(name);
    if (value !== null) out.set(name, value);
  }
  out.set("x-rz-proxy-secret", secret);
  if (ip) out.set("x-rz-client-ip", ip);
  return out;
}

/** A redirect to the backend's own /api/ path, as a relative URL; anything else is dropped. */
export function relativeLocation(location: string, target: URL): string | null {
  let url: URL;
  try {
    url = new URL(location, target);
  } catch {
    return null;
  }
  if (url.origin !== target.origin || !url.pathname.startsWith("/api/")) return null;
  return url.pathname + url.search + url.hash;
}

export function copyResponseHeaders(upstream: Headers, target: URL): Headers {
  const out = new Headers();
  for (const name of RESPONSE_HEADER_ALLOWLIST) {
    const value = upstream.get(name);
    if (value !== null) out.set(name, value);
  }
  // fetch decodes gzip/br bodies, so a compressed length would no longer match the bytes we send.
  const length = upstream.get("content-length");
  if (length !== null && !upstream.has("content-encoding")) out.set("content-length", length);
  for (const cookie of upstream.getSetCookie()) out.append("set-cookie", cookie);
  const location = upstream.get("location");
  const relative = location === null ? null : relativeLocation(location, target);
  if (relative) out.set("location", relative);
  return out;
}

const TOO_LARGE = Symbol("too large");

/** Reads the whole body, stopping as soon as it passes `max` bytes. */
export async function readBody(
  request: Request,
  max: number,
): Promise<Uint8Array<ArrayBuffer> | null | typeof TOO_LARGE> {
  if (request.method === "GET" || request.method === "HEAD" || !request.body) return null;
  if (Number(request.headers.get("content-length") ?? 0) > max) return TOO_LARGE;
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > max) {
      await reader.cancel();
      return TOO_LARGE;
    }
    chunks.push(value);
  }
  if (size === 0) return null;
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

export function createRelay(options: RelayOptions = {}) {
  const timeoutMs = options.timeoutMs ?? RELAY_TIMEOUT_MS;
  const maxBodyBytes = options.maxBodyBytes ?? MAX_BODY_BYTES;
  const readEnv =
    options.readEnv ??
    (() => ({
      BACKEND_ORIGIN: process.env.BACKEND_ORIGIN,
      PROXY_SHARED_SECRET: process.env.PROXY_SHARED_SECRET,
    }));
  const getFetch = options.getFetch ?? (() => globalThis.fetch);

  return async function relay(request: Request): Promise<Response> {
    const config = readConfig(readEnv());
    if ("invalid" in config) {
      console.error(`API relay: ${config.invalid} is missing or invalid`);
      return json(500, { detail: "The API relay is not configured.", code: "relay_misconfigured" });
    }

    const target = buildTarget(request.url, config.origin);
    if (target === 400) return json(400, { detail: "Invalid path.", code: "bad_request" });
    if (target === 404) return json(404, { detail: "Not found.", code: "not_found" });

    const headers = forwardRequestHeaders(
      request.headers,
      config.secret,
      clientIp(request.headers),
    );

    let body: Awaited<ReturnType<typeof readBody>>;
    try {
      body = await readBody(request, maxBodyBytes);
    } catch {
      return json(400, { detail: "The request body could not be read.", code: "bad_request" });
    }
    if (body === TOO_LARGE) {
      return json(413, { detail: "The request is too large.", code: "payload_too_large" });
    }

    // The timer covers the wait for response headers only, so a long download isn't cut off.
    const timeout = new AbortController();
    const timer = setTimeout(() => timeout.abort(), timeoutMs);
    let upstream: Response;
    try {
      upstream = await getFetch()(target, {
        method: request.method,
        headers,
        body,
        redirect: "manual",
        cache: "no-store",
        signal: AbortSignal.any([request.signal, timeout.signal]),
      });
    } catch (error) {
      console.warn(`API relay: backend unavailable (${(error as Error).name})`);
      return backendWaking();
    } finally {
      clearTimeout(timer);
    }

    const { status } = upstream;
    const contentType = upstream.headers.get("content-type") ?? "";
    if (GATEWAY_STATUSES.has(status) && !contentType.includes("json")) {
      // Render's own error page while the service starts or restarts.
      await upstream.body?.cancel();
      return backendWaking();
    }
    if (status < 200 || status > 599) {
      await upstream.body?.cancel();
      return json(502, { detail: "Unexpected response from the server.", code: "bad_gateway" });
    }

    const noBody = NULL_BODY_STATUSES.has(status) || request.method === "HEAD";
    if (noBody) await upstream.body?.cancel();
    return new Response(noBody ? null : upstream.body, {
      status,
      headers: copyResponseHeaders(upstream.headers, target),
    });
  };
}
