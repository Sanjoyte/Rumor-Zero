import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setAccessTokenGetter } from "@/lib/api/client";
import { AUTH_PATHS, fetchMe, login, logout, refresh, signup } from "./auth-api";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  // A managed token exists, but the auth calls must never send it.
  setAccessTokenGetter(() => "managed-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessTokenGetter(() => null);
});

function sent(call = 0) {
  const [url, init] = fetchMock.mock.calls[call];
  return {
    url: String(url),
    method: (init as RequestInit).method,
    body: (init as RequestInit).body,
    headers: new Headers((init as RequestInit).headers),
  };
}

describe("auth API", () => {
  it("logs in with email and password and reads meta.access_token", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ status: 200, meta: { is_authenticated: true, access_token: "access-1" } }),
    );
    expect(await login("ada@example.test", "pw")).toBe("access-1");
    const request = sent();
    expect(request.url).toBe(`/api${AUTH_PATHS.login}`);
    expect(request.url).toBe("/api/auth/app/v1/auth/login");
    expect(request.method).toBe("POST");
    expect(request.body).toBe('{"email":"ada@example.test","password":"pw"}');
    expect(request.headers.has("authorization")).toBe(false);
    expect(request.headers.get("x-requested-with")).toBe("rumor-zero");
  });

  it("signs up with the Turnstile token", async () => {
    fetchMock.mockResolvedValue(Response.json({ status: 200, meta: { access_token: "access-2" } }));
    const token = await signup({
      email: "a@b.c",
      username: "ada",
      password: "pw",
      turnstileToken: "XXXX.DUMMY.TOKEN.XXXX",
    });
    expect(token).toBe("access-2");
    expect(sent().url).toBe("/api/auth/app/v1/auth/signup");
    expect(JSON.parse(String(sent().body))).toEqual({
      email: "a@b.c",
      username: "ada",
      password: "pw",
      turnstile_token: "XXXX.DUMMY.TOKEN.XXXX",
    });
  });

  it("refreshes with an empty body and reads data.access_token", async () => {
    fetchMock.mockResolvedValue(Response.json({ status: 200, data: { access_token: "access-3" } }));
    expect(await refresh()).toBe("access-3");
    expect(sent().url).toBe("/api/auth/app/v1/tokens/refresh");
    expect(sent().body).toBeUndefined();
    expect(sent().headers.has("authorization")).toBe(false);
  });

  it("logs out with a POST and resolves on 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(logout()).resolves.toBeUndefined();
    expect(sent().url).toBe("/api/auth/logout/");
    expect(sent().method).toBe("POST");
  });

  it("loads /me with the token it is given", async () => {
    fetchMock.mockResolvedValue(Response.json({ id: "u-1", username: "ada" }));
    expect(await fetchMe("fresh-token")).toMatchObject({ username: "ada" });
    expect(sent().url).toBe("/api/v1/me/");
    expect(sent().headers.get("authorization")).toBe("Bearer fresh-token");
  });

  it("throws allauth errors with their codes and params", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        {
          status: 400,
          errors: [{ code: "email_password_mismatch", param: "password", message: "No." }],
        },
        { status: 400 },
      ),
    );
    await expect(login("a@b.c", "bad")).rejects.toMatchObject({
      status: 400,
      code: "email_password_mismatch",
      fieldErrors: { password: ["No."] },
    });
  });

  it("treats a 200 without an access token as an error", async () => {
    fetchMock.mockResolvedValue(Response.json({ status: 200, data: {} }));
    await expect(refresh()).rejects.toMatchObject({ code: "no_access_token" });
  });
});
