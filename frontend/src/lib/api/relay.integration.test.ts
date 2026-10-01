// @vitest-environment node
/**
 * The relay against a real HTTP server with Node's real fetch (undici). Mocked fetch can't show
 * what actually goes over the wire: Content-Length vs chunked bodies, repeated Set-Cookie headers,
 * transparent gzip decoding, refused connections and timeouts.
 */
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { gzipSync } from "node:zlib";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { createRelay } from "./relay";

const SECRET = "test-relay-secret";
let server: Server;
let origin: string;

function readAll(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

async function handle(req: IncomingMessage, res: ServerResponse) {
  const body = await readAll(req);
  switch (new URL(req.url ?? "/", "http://x").pathname) {
    case "/api/echo/":
      res.setHeader("content-type", "application/json");
      res.end(
        JSON.stringify({
          method: req.method,
          path: req.url,
          contentLength: req.headers["content-length"] ?? null,
          transferEncoding: req.headers["transfer-encoding"] ?? null,
          body: body.toString("utf8"),
          secretMatches: req.headers["x-rz-proxy-secret"] === SECRET,
          clientIp: req.headers["x-rz-client-ip"] ?? null,
          host: req.headers.host,
          forwardedFor: req.headers["x-forwarded-for"] ?? null,
          userAgent: req.headers["user-agent"] ?? null,
        }),
      );
      return;
    case "/api/cookies/":
      res.setHeader("set-cookie", ["rz_refresh=a; Path=/api/auth/; HttpOnly", "other=b; Path=/"]);
      res.setHeader("content-type", "application/json");
      res.end("{}");
      return;
    case "/api/etag/":
      res.setHeader("etag", '"v1"');
      res.setHeader("cache-control", "public, max-age=31536000, immutable");
      if (req.headers["if-none-match"] === '"v1"') {
        res.statusCode = 304;
        res.end();
      } else {
        res.setHeader("content-type", "image/webp");
        res.end(Buffer.from([1, 2, 3]));
      }
      return;
    case "/api/gzip/": {
      const zipped = gzipSync(Buffer.from('{"message":"hello, compressed world"}'));
      res.setHeader("content-type", "application/json");
      res.setHeader("content-encoding", "gzip");
      res.setHeader("content-length", String(zipped.byteLength));
      res.end(zipped);
      return;
    }
    case "/api/hang/":
      return; // never answers
    case "/api/slow-body/":
      res.setHeader("content-type", "text/plain");
      res.write("first,");
      setTimeout(() => res.end("second"), 300);
      return;
    default:
      res.statusCode = 404;
      res.end();
  }
}

function relay(options: { timeoutMs?: number; backendOrigin?: string } = {}) {
  return createRelay({
    readEnv: () => ({
      BACKEND_ORIGIN: options.backendOrigin ?? origin,
      PROXY_SHARED_SECRET: SECRET,
    }),
    timeoutMs: options.timeoutMs,
  });
}

beforeAll(async () => {
  server = createServer((req, res) => void handle(req, res));
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterAll(async () => {
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
});

describe("relay over real HTTP", () => {
  it("sends a buffered body with Content-Length, never chunked", async () => {
    const payload = JSON.stringify({ content: "Ünïcödé text — 100 °C" });
    const response = await relay()(
      new Request("http://localhost:3000/api/echo/?x=1", {
        method: "POST",
        body: payload,
        headers: {
          "content-type": "application/json",
          "user-agent": "Browser/1.0",
          "x-forwarded-for": "198.51.100.4",
          "x-rz-proxy-secret": "spoofed",
        },
      }),
    );
    const echo = await response.json();
    expect(echo).toMatchObject({
      method: "POST",
      path: "/api/echo/?x=1",
      contentLength: String(Buffer.byteLength(payload)),
      transferEncoding: null,
      body: payload,
      secretMatches: true,
      clientIp: "198.51.100.4",
      host: new URL(origin).host,
      forwardedFor: null,
      userAgent: "Browser/1.0",
    });
  });

  it("also sends a streamed (length-less) client body with a Content-Length", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("part one, "));
        controller.enqueue(new TextEncoder().encode("part two"));
        controller.close();
      },
    });
    const response = await relay()(
      new Request("http://localhost:3000/api/echo/", {
        method: "PUT",
        body: stream,
        duplex: "half",
      } as RequestInit),
    );
    expect(await response.json()).toMatchObject({
      method: "PUT",
      contentLength: "18",
      transferEncoding: null,
      body: "part one, part two",
    });
  });

  it("keeps both Set-Cookie headers", async () => {
    const response = await relay()(new Request("http://localhost:3000/api/cookies/"));
    expect(response.headers.getSetCookie()).toEqual([
      "rz_refresh=a; Path=/api/auth/; HttpOnly",
      "other=b; Path=/",
    ]);
  });

  it("passes If-None-Match up and a 304 down unchanged", async () => {
    const first = await relay()(new Request("http://localhost:3000/api/etag/"));
    expect(first.status).toBe(200);
    expect(first.headers.get("etag")).toBe('"v1"');
    expect(new Uint8Array(await first.arrayBuffer())).toEqual(new Uint8Array([1, 2, 3]));
    const second = await relay()(
      new Request("http://localhost:3000/api/etag/", { headers: { "if-none-match": '"v1"' } }),
    );
    expect(second.status).toBe(304);
    expect(second.body).toBeNull();
    expect(second.headers.get("etag")).toBe('"v1"');
    expect(second.headers.get("cache-control")).toBe("public, max-age=31536000, immutable");
  });

  it("returns a decoded gzip body without the compressed Content-Length", async () => {
    const response = await relay()(new Request("http://localhost:3000/api/gzip/"));
    expect(response.headers.has("content-length")).toBe(false);
    expect(await response.json()).toEqual({ message: "hello, compressed world" });
  });

  it("answers 503 backend_waking when the backend refuses the connection", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const closed = createServer();
    await new Promise<void>((resolve) => closed.listen(0, "127.0.0.1", resolve));
    const port = (closed.address() as AddressInfo).port;
    await new Promise((resolve) => closed.close(resolve));
    const response = await relay({ backendOrigin: `http://127.0.0.1:${port}` })(
      new Request("http://localhost:3000/api/health/"),
    );
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ code: "backend_waking" });
  });

  it("answers 503 backend_waking when no headers arrive in time", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const started = Date.now();
    const response = await relay({ timeoutMs: 200 })(
      new Request("http://localhost:3000/api/hang/"),
    );
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ code: "backend_waking" });
    expect(Date.now() - started).toBeLessThan(5000);
  });

  it("does not cut off a body that is still arriving after the timeout", async () => {
    const response = await relay({ timeoutMs: 100 })(
      new Request("http://localhost:3000/api/slow-body/"),
    );
    expect(response.status).toBe(200);
    expect(await response.text()).toBe("first,second");
  });
});
