// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  api,
  apiFetch,
  baseFor,
  normalizeError,
  setAccessTokenGetter,
  setUnauthorizedHandler,
} from "./client";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

describe("normalizeError", () => {
  it("reads DRF's {detail, code}", () => {
    const error = normalizeError(403, {
      detail: "Verify your email first.",
      code: "email_unverified",
    });
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 403,
      code: "email_unverified",
      detail: "Verify your email first.",
      fieldErrors: {},
      retryAfter: null,
    });
  });

  it("flattens DRF field errors, including nested and non-field ones", () => {
    const error = normalizeError(400, {
      content: ["Ensure this field has no more than 500 characters."],
      sources: [{}, { value: ["Enter a valid URL or DOI."] }],
      non_field_errors: ["Opinions can't have sources."],
    });
    expect(error.code).toBe("invalid");
    expect(error.detail).toBe("Ensure this field has no more than 500 characters.");
    expect(error.fieldErrors).toEqual({
      content: ["Ensure this field has no more than 500 characters."],
      "sources.1.value": ["Enter a valid URL or DOI."],
      non_field_errors: ["Opinions can't have sources."],
    });
  });

  it("reads allauth's errors[] by param", () => {
    const error = normalizeError(400, {
      status: 400,
      errors: [
        { code: "email_taken", param: "email", message: "A user is already registered." },
        { code: "invalid", message: "Something else." },
      ],
    });
    expect(error.code).toBe("email_taken");
    expect(error.detail).toBe("A user is already registered.");
    expect(error.fieldErrors).toEqual({
      email: ["A user is already registered."],
      non_field_errors: ["Something else."],
    });
  });

  it("handles allauth's 401, which has flows instead of errors", () => {
    const error = normalizeError(401, {
      status: 401,
      data: { flows: [{ id: "login" }] },
      meta: { is_authenticated: false },
    });
    expect(error.code).toBe("not_authenticated");
    expect(error.fieldErrors).toEqual({});
  });

  it("keeps the relay's backend_waking and reads Retry-After", () => {
    const error = normalizeError(
      503,
      { detail: "The server is waking up. Try again in a minute.", code: "backend_waking" },
      new Headers({ "retry-after": "30" }),
    );
    expect(error).toMatchObject({ code: "backend_waking", retryAfter: 30 });
    const throttled = normalizeError(
      429,
      { detail: "Request was throttled.", code: "throttled" },
      new Headers({ "retry-after": "120" }),
    );
    expect(throttled.retryAfter).toBe(120);
  });

  it("falls back to a code by status for non-JSON bodies and network failures", () => {
    expect(normalizeError(404, null).code).toBe("not_found");
    expect(normalizeError(500, "<html>").code).toBe("http_500");
    const network = normalizeError(0, null);
    expect(network.code).toBe("network_error");
    expect(network.detail).toMatch(/connection/);
  });
});

describe("apiFetch", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    setAccessTokenGetter(() => null);
    setUnauthorizedHandler(null);
  });

  const sent = (call = 0) => {
    const [url, init] = fetchMock.mock.calls[call];
    return { url: String(url), init: init as RequestInit, headers: new Headers(init?.headers) };
  };

  it("calls the relative /api base with JSON headers and X-Requested-With", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { status: "ok" }));
    expect(await api.get("/health/")).toEqual({ status: "ok" });
    const { url, init, headers } = sent();
    expect(url).toBe("/api/health/");
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("same-origin");
    expect(headers.get("accept")).toBe("application/json");
    expect(headers.get("x-requested-with")).toBe("rumor-zero");
    expect(headers.has("authorization")).toBe(false);
  });

  it("sends JSON bodies and the bearer token", async () => {
    setAccessTokenGetter(() => "token-1");
    fetchMock.mockResolvedValue(jsonResponse(201, { id: "p1" }));
    await api.post("/v1/posts/", { content: "x", post_type: "opinion" });
    const { init, headers } = sent();
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"content":"x","post_type":"opinion"}');
    expect(headers.get("content-type")).toBe("application/json");
    expect(headers.get("authorization")).toBe("Bearer token-1");
  });

  it("sends FormData as it is", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const form = new FormData();
    form.set("photo", new Blob(["x"]), "photo.png");
    expect(await api.put("/v1/me/avatar/", form)).toBeUndefined();
    expect(sent().init.body).toBe(form);
    expect(sent().headers.has("content-type")).toBe(false);
  });

  it("supports every method helper", async () => {
    fetchMock.mockImplementation(async () => new Response(null, { status: 204 }));
    await api.patch("/v1/me/", { bio: "" });
    await api.del("/v1/posts/p1/");
    expect(sent(0).init.method).toBe("PATCH");
    expect(sent(1).init.method).toBe("DELETE");
  });

  it("throws ApiError for error responses", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(409, { detail: "Already reported.", code: "already_reported" }),
    );
    await expect(api.post("/v1/posts/p1/report/", {})).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      code: "already_reported",
    });
  });

  it("turns a network failure into network_error, but rethrows an abort", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(api.get("/v1/posts/")).rejects.toMatchObject({ code: "network_error", status: 0 });
    const controller = new AbortController();
    controller.abort();
    fetchMock.mockRejectedValueOnce(new DOMException("aborted", "AbortError"));
    await expect(api.get("/v1/posts/", { signal: controller.signal })).rejects.toMatchObject({
      name: "AbortError",
    });
  });

  it("refuses paths that would leave the /api base", async () => {
    await expect(apiFetch("v1/posts/")).rejects.toThrow(/one "\/"/);
    await expect(apiFetch("//evil.example/")).rejects.toThrow(/one "\/"/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("retries once after the 401 hook refreshes, with the new token", async () => {
    let token = "old";
    setAccessTokenGetter(() => token);
    const handler = vi.fn(async () => {
      token = "new";
      return true;
    });
    setUnauthorizedHandler(handler);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Expired.", code: "not_authenticated" }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    expect(await api.get("/v1/me/")).toEqual({ ok: true });
    expect(handler).toHaveBeenCalledTimes(1);
    expect(sent(0).headers.get("authorization")).toBe("Bearer old");
    expect(sent(1).headers.get("authorization")).toBe("Bearer new");
  });

  it("never loops: a second 401 after the retry is thrown", async () => {
    setUnauthorizedHandler(async () => true);
    fetchMock.mockImplementation(async () =>
      jsonResponse(401, { detail: "No.", code: "not_authenticated" }),
    );
    await expect(api.get("/v1/me/")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("throws the 401 when the hook declines or there is none", async () => {
    fetchMock.mockImplementation(async () =>
      jsonResponse(401, { detail: "No.", code: "not_authenticated" }),
    );
    await expect(api.get("/v1/me/")).rejects.toMatchObject({ status: 401 });
    setUnauthorizedHandler(async () => false);
    await expect(api.get("/v1/me/")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shares one hook call between concurrent 401s", async () => {
    let release!: (value: boolean) => void;
    const handler = vi.fn(() => new Promise<boolean>((resolve) => (release = resolve)));
    setUnauthorizedHandler(handler);
    let calls = 0;
    fetchMock.mockImplementation(async () =>
      ++calls <= 2 ? jsonResponse(401, { detail: "Expired." }) : jsonResponse(200, { ok: true }),
    );
    const both = Promise.all([api.get("/v1/a/"), api.get("/v1/b/")]);
    await vi.waitFor(() => expect(handler).toHaveBeenCalled());
    release(true);
    expect(await both).toEqual([{ ok: true }, { ok: true }]);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("skips the 401 hook for /auth/ endpoints", async () => {
    const handler = vi.fn(async () => true);
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValue(
      jsonResponse(401, { status: 401, meta: { is_authenticated: false } }),
    );
    await expect(api.post("/auth/app/v1/auth/login", {})).rejects.toMatchObject({ status: 401 });
    expect(handler).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("uses the relay for every call type", () => {
    expect(baseFor("app")).toBe("/api");
    expect(baseFor("auth")).toBe("/api");
  });
});
