// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildTarget,
  clientIp,
  copyResponseHeaders,
  createRelay,
  forwardRequestHeaders,
  readConfig,
  relativeLocation,
} from "./relay";

const ORIGIN = "https://api.example.test";
const SECRET = "test-relay-secret";
const env = { BACKEND_ORIGIN: ORIGIN, PROXY_SHARED_SECRET: SECRET };

type FetchArgs = [URL, RequestInit];

function relayWith(
  respond: (url: URL, init: RequestInit) => Response | Promise<Response>,
  options: { timeoutMs?: number; maxBodyBytes?: number; env?: typeof env } = {},
) {
  const fetchMock = vi.fn(async (url: URL, init: RequestInit) => respond(url, init));
  const relay = createRelay({
    readEnv: () => options.env ?? env,
    getFetch: () => fetchMock as unknown as typeof fetch,
    timeoutMs: options.timeoutMs,
    maxBodyBytes: options.maxBodyBytes,
  });
  const sent = () => fetchMock.mock.calls[0] as unknown as FetchArgs;
  return { relay, fetchMock, sent };
}

const ok = () =>
  new Response('{"status":"ok"}', { headers: { "content-type": "application/json" } });

afterEach(() => {
  vi.restoreAllMocks();
});

describe("readConfig", () => {
  it("accepts an https origin, or http only on loopback", () => {
    expect(readConfig(env)).toEqual({ origin: ORIGIN, secret: SECRET });
    for (const origin of ["http://localhost:8000", "http://127.0.0.1:8000", "http://[::1]:8000"]) {
      expect(readConfig({ ...env, BACKEND_ORIGIN: origin })).toHaveProperty("origin");
    }
  });

  it("names the wrong variable and never returns its value", () => {
    const bad = [
      undefined,
      "",
      "not a url",
      "http://api.example.test",
      "https://api.example.test/api",
      "ftp://api.example.test",
    ];
    for (const BACKEND_ORIGIN of bad) {
      expect(readConfig({ ...env, BACKEND_ORIGIN })).toEqual({ invalid: "BACKEND_ORIGIN" });
    }
    expect(readConfig({ ...env, PROXY_SHARED_SECRET: "" })).toEqual({
      invalid: "PROXY_SHARED_SECRET",
    });
  });
});

describe("buildTarget", () => {
  it("keeps the path, trailing slash and query", () => {
    const target = buildTarget("http://localhost:3000/api/health/?a=1&b=2", ORIGIN);
    expect(String(target)).toBe(`${ORIGIN}/api/health/?a=1&b=2`);
  });

  it("refuses encoded separators", () => {
    for (const path of ["/api/%2F..%2Fadmin/", "/api/a%2fb/", "/api/%5C/", "/api/%00/"]) {
      expect(buildTarget(`http://localhost:3000${path}`, ORIGIN)).toBe(400);
    }
  });

  it("refuses anything outside /api/", () => {
    expect(buildTarget("http://localhost:3000/api/../secret-admin/", ORIGIN)).toBe(404);
    expect(buildTarget("http://localhost:3000/api/%2e%2e/secret-admin/", ORIGIN)).toBe(404);
    expect(buildTarget("http://localhost:3000/api", ORIGIN)).toBe(404);
    expect(buildTarget("http://localhost:3000/secret-admin/", ORIGIN)).toBe(404);
  });
});

describe("clientIp", () => {
  it("prefers cf-connecting-ip, then the right-most x-forwarded-for entry", () => {
    const both = new Headers({ "cf-connecting-ip": "203.0.113.7", "x-forwarded-for": "1.1.1.1" });
    expect(clientIp(both)).toBe("203.0.113.7");
    expect(clientIp(new Headers({ "x-forwarded-for": "6.6.6.6, 198.51.100.4 " }))).toBe(
      "198.51.100.4",
    );
    expect(clientIp(new Headers({ "x-forwarded-for": "::1" }))).toBe("::1");
  });

  it("ignores values that aren't IP literals", () => {
    expect(clientIp(new Headers({ "cf-connecting-ip": "evil<script>" }))).toBeNull();
    expect(clientIp(new Headers({ "x-forwarded-for": "1.1.1.1, not-an-ip" }))).toBeNull();
    expect(clientIp(new Headers())).toBeNull();
  });
});

describe("forwardRequestHeaders", () => {
  const incoming = new Headers({
    accept: "application/json",
    authorization: "Bearer abc",
    "content-type": "application/json",
    cookie: "rz_refresh=r1",
    origin: "http://localhost:3000",
    "x-requested-with": "rumor-zero",
    "x-password-reset-key": "0123abcd-1abc-0fed",
    "if-none-match": '"v1"',
    "if-modified-since": "Wed, 30 Sep 2026 12:00:00 GMT",
    "user-agent": "Browser/1.0",
    host: "localhost:3000",
    connection: "keep-alive",
    "keep-alive": "timeout=5",
    "transfer-encoding": "chunked",
    "content-length": "12",
    "x-forwarded-for": "6.6.6.6",
    "x-forwarded-host": "evil.example",
    "x-rz-proxy-secret": "spoofed",
    "x-rz-client-ip": "6.6.6.6",
    "x-rz-cron-secret": "spoofed",
  });

  it("keeps only the allow-list, then adds the secret and client IP", () => {
    const out = forwardRequestHeaders(incoming, SECRET, "203.0.113.7");
    expect(Object.fromEntries(out)).toEqual({
      accept: "application/json",
      authorization: "Bearer abc",
      "content-type": "application/json",
      cookie: "rz_refresh=r1",
      origin: "http://localhost:3000",
      "x-requested-with": "rumor-zero",
      "x-password-reset-key": "0123abcd-1abc-0fed",
      "if-none-match": '"v1"',
      "if-modified-since": "Wed, 30 Sep 2026 12:00:00 GMT",
      "user-agent": "Browser/1.0",
      "x-rz-proxy-secret": SECRET,
      "x-rz-client-ip": "203.0.113.7",
    });
  });

  it("drops a spoofed client IP header when there is no usable IP", () => {
    const out = forwardRequestHeaders(incoming, SECRET, null);
    expect(out.has("x-rz-client-ip")).toBe(false);
    expect(out.get("x-rz-proxy-secret")).toBe(SECRET);
  });
});

describe("copyResponseHeaders", () => {
  const target = new URL(`${ORIGIN}/api/thing/`);

  it("keeps the allow-list and every Set-Cookie, and drops the rest", () => {
    const upstream = new Headers({
      "content-type": "application/json",
      "cache-control": "private, max-age=60",
      etag: '"v1"',
      "last-modified": "Wed, 30 Sep 2026 12:00:00 GMT",
      "content-disposition": 'attachment; filename="export.json"',
      "x-content-type-options": "nosniff",
      "content-security-policy": "default-src 'none'; sandbox",
      "retry-after": "120",
      "content-length": "15",
      server: "gunicorn",
      "x-frame-options": "DENY",
      vary: "Accept",
      connection: "close",
    });
    upstream.append("set-cookie", "a=1; Path=/api/auth/; HttpOnly");
    upstream.append("set-cookie", "b=2; Path=/; SameSite=Lax");
    const out = copyResponseHeaders(upstream, target);
    expect(out.getSetCookie()).toEqual([
      "a=1; Path=/api/auth/; HttpOnly",
      "b=2; Path=/; SameSite=Lax",
    ]);
    expect(out.get("content-length")).toBe("15");
    for (const dropped of ["server", "x-frame-options", "vary", "connection"]) {
      expect(out.has(dropped)).toBe(false);
    }
    expect(out.get("content-security-policy")).toBe("default-src 'none'; sandbox");
  });

  it("drops Content-Length when the upstream body was compressed", () => {
    const out = copyResponseHeaders(
      new Headers({ "content-encoding": "gzip", "content-length": "31" }),
      target,
    );
    expect(out.has("content-length")).toBe(false);
    expect(out.has("content-encoding")).toBe(false);
  });

  it("rewrites a backend /api/ Location to a relative one and drops any other", () => {
    expect(relativeLocation("/api/health/", target)).toBe("/api/health/");
    expect(relativeLocation(`${ORIGIN}/api/a/?x=1`, target)).toBe("/api/a/?x=1");
    expect(relativeLocation(`${ORIGIN}/secret-admin/`, target)).toBeNull();
    expect(relativeLocation("https://elsewhere.example/api/a/", target)).toBeNull();
    const out = copyResponseHeaders(new Headers({ location: `${ORIGIN}/api/b/` }), target);
    expect(out.get("location")).toBe("/api/b/");
  });
});

describe("createRelay", () => {
  it("forwards a GET to the backend with the secret and the client IP", async () => {
    const { relay, sent } = relayWith(ok);
    const response = await relay(
      new Request("http://localhost:3000/api/health/", {
        headers: { "x-forwarded-for": "198.51.100.4", "x-rz-proxy-secret": "spoofed" },
      }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
    const [url, init] = sent();
    expect(String(url)).toBe(`${ORIGIN}/api/health/`);
    expect(init.method).toBe("GET");
    expect(init.body).toBeNull();
    expect(init.redirect).toBe("manual");
    expect(init.cache).toBe("no-store");
    const headers = new Headers(init.headers);
    expect(headers.get("x-rz-proxy-secret")).toBe(SECRET);
    expect(headers.get("x-rz-client-ip")).toBe("198.51.100.4");
  });

  it("passes the method and body through, without the client's Content-Length", async () => {
    const { relay, sent } = relayWith(() => new Response(null, { status: 201 }));
    const payload = JSON.stringify({ content: "Water boils at 100 °C at sea level." });
    for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
      const response = await relay(
        new Request("http://localhost:3000/api/v1/posts/", {
          method,
          body: payload,
          headers: { "content-type": "application/json", "content-length": "999" },
        }),
      );
      expect(response.status).toBe(201);
    }
    const [, init] = sent();
    expect(init.method).toBe("POST");
    expect(new TextDecoder().decode(init.body as Uint8Array)).toBe(payload);
    expect(new Headers(init.headers).has("content-length")).toBe(false);
  });

  it("passes a multipart photo upload through byte for byte, boundary included (Part 14B)", async () => {
    const { relay, sent } = relayWith(() => new Response('{"id":"u-1"}', { status: 200 }));
    const form = new FormData();
    const photo = new Uint8Array(4096).map((_, index) => (index * 7) % 256);
    form.set("file", new Blob([photo], { type: "image/jpeg" }), "photo.jpg");
    const request = new Request("http://localhost:3000/api/v1/me/avatar/", {
      method: "PUT",
      body: form,
    });
    const contentType = request.headers.get("content-type")!;
    const original = new Uint8Array(await request.clone().arrayBuffer());
    expect(contentType).toMatch(/^multipart\/form-data; boundary=/);

    const response = await relay(request);

    expect(response.status).toBe(200);
    const [, init] = sent();
    expect(init.method).toBe("PUT");
    // The boundary in the header is the one inside the body: the backend can still parse it.
    expect(new Headers(init.headers).get("content-type")).toBe(contentType);
    expect(new Uint8Array(init.body as ArrayBuffer)).toEqual(original);
  });

  it("lets a 5 MB photo through under the default limit and refuses 6 MB + 1", async () => {
    const { relay, fetchMock } = relayWith(() => new Response(null, { status: 200 }));
    const put = (bytes: number) =>
      relay(
        new Request("http://localhost:3000/api/v1/me/avatar/", {
          method: "PUT",
          body: new Uint8Array(bytes),
          headers: { "content-type": "application/octet-stream" },
        }),
      );
    expect((await put(5 * 1024 * 1024 + 64 * 1024)).status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const tooBig = await put(6 * 1024 * 1024 + 1);
    expect(tooBig.status).toBe(413);
    expect(await tooBig.json()).toMatchObject({ code: "payload_too_large" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("sends no body for HEAD and returns none", async () => {
    const { relay, sent } = relayWith(
      () => new Response("ignored", { headers: { "content-length": "7" } }),
    );
    const response = await relay(new Request("http://localhost:3000/api/x/", { method: "HEAD" }));
    expect(sent()[1].body).toBeNull();
    expect(response.body).toBeNull();
    expect(response.headers.get("content-length")).toBe("7");
  });

  it("passes a 304 through with its cache headers and no body", async () => {
    const { relay, sent } = relayWith(
      () =>
        new Response(null, {
          status: 304,
          headers: { etag: '"v1"', "cache-control": "public, max-age=31536000, immutable" },
        }),
    );
    const response = await relay(
      new Request("http://localhost:3000/api/v1/avatars/u/1-96.webp", {
        headers: { "if-none-match": '"v1"' },
      }),
    );
    expect(new Headers(sent()[1].headers).get("if-none-match")).toBe('"v1"');
    expect(response.status).toBe(304);
    expect(response.body).toBeNull();
    expect(response.headers.get("etag")).toBe('"v1"');
    expect(response.headers.get("cache-control")).toBe("public, max-age=31536000, immutable");
  });

  it("returns every Set-Cookie from the backend", async () => {
    const { relay } = relayWith(() => {
      const headers = new Headers();
      headers.append("set-cookie", "rz_refresh=a; Path=/api/auth/; HttpOnly");
      headers.append("set-cookie", "other=b; Path=/");
      return new Response("{}", { headers });
    });
    const response = await relay(new Request("http://localhost:3000/api/auth/x/"));
    expect(response.headers.getSetCookie()).toHaveLength(2);
  });

  it("answers 503 backend_waking when the backend is unreachable", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const { relay } = relayWith(() => {
      throw new TypeError("fetch failed");
    });
    const response = await relay(new Request("http://localhost:3000/api/health/"));
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ code: "backend_waking" });
    expect(response.headers.get("retry-after")).toBe("30");
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("answers 503 backend_waking when no headers arrive before the timeout", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const { relay } = relayWith(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => reject(init.signal?.reason));
        }),
      { timeoutMs: 20 },
    );
    const response = await relay(new Request("http://localhost:3000/api/health/"));
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ code: "backend_waking" });
  });

  it("maps Render's non-JSON gateway errors to backend_waking, but keeps JSON ones", async () => {
    const html = relayWith(
      () =>
        new Response("<html>502</html>", { status: 502, headers: { "content-type": "text/html" } }),
    );
    expect(
      await (await html.relay(new Request("http://localhost:3000/api/x/"))).json(),
    ).toMatchObject({ code: "backend_waking" });
    const jsonError = relayWith(
      () =>
        new Response('{"status":"error","database":"error","cache":"ok"}', {
          status: 503,
          headers: { "content-type": "application/json" },
        }),
    );
    const response = await jsonError.relay(new Request("http://localhost:3000/api/health/deep/"));
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ database: "error" });
  });

  it("maps a status outside 200-599 to 502", async () => {
    const { relay } = relayWith(
      () => ({ status: 101, headers: new Headers(), body: null }) as unknown as Response,
    );
    const response = await relay(new Request("http://localhost:3000/api/x/"));
    expect(response.status).toBe(502);
    expect(await response.json()).toMatchObject({ code: "bad_gateway" });
  });

  it("refuses a body over the limit before calling the backend", async () => {
    const { relay, fetchMock } = relayWith(ok, { maxBodyBytes: 10 });
    const declared = await relay(
      new Request("http://localhost:3000/api/v1/me/avatar/", {
        method: "PUT",
        body: "x".repeat(11),
      }),
    );
    expect(declared.status).toBe(413);
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new Uint8Array(6));
        controller.enqueue(new Uint8Array(6));
        controller.close();
      },
    });
    const chunked = await relay(
      new Request("http://localhost:3000/api/v1/me/avatar/", {
        method: "PUT",
        body: stream,
        duplex: "half",
      } as RequestInit),
    );
    expect(chunked.status).toBe(413);
    expect(await chunked.json()).toMatchObject({ code: "payload_too_large" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses paths outside /api/ and encoded separators without calling the backend", async () => {
    const { relay, fetchMock } = relayWith(ok);
    expect((await relay(new Request("http://localhost:3000/api/a%2Fb/"))).status).toBe(400);
    expect((await relay(new Request("http://localhost:3000/api/../admin/"))).status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("answers 500 relay_misconfigured and logs only the variable name", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const { relay, fetchMock } = relayWith(ok, {
      env: { BACKEND_ORIGIN: "http://api.example.test", PROXY_SHARED_SECRET: SECRET },
    });
    const response = await relay(new Request("http://localhost:3000/api/health/"));
    expect(response.status).toBe(500);
    const text = await response.text();
    expect(JSON.parse(text)).toMatchObject({ code: "relay_misconfigured" });
    expect(text).not.toContain(SECRET);
    expect(text).not.toContain("api.example.test");
    expect(String(error.mock.calls[0][0])).toBe("API relay: BACKEND_ORIGIN is missing or invalid");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
