import { act, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import { AuthProvider, resetBrowserSessionForTests, useAuth } from "./AuthProvider";
import { getAccessToken, setAccessToken } from "./token-store";

function segment(value: object): string {
  return btoa(JSON.stringify(value)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}
const token = (n: number) =>
  `${segment({ alg: "HS256" })}.${segment({ sub: "u-1", iat: 1_800_000_000 + n, exp: 1_800_000_900 + n })}.sig`;
const ME = { id: "u-1", username: "ada", display_name: "Ada", is_email_verified: false };

function Probe() {
  const { status, user } = useAuth();
  return <p>{`${status}:${user === null ? "no user" : user.username}`}</p>;
}

let calls: string[] = [];
let refreshes = 0;
const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
  const path = String(url);
  calls.push(`${init?.method ?? "GET"} ${path}`);
  if (path.endsWith("/tokens/refresh")) {
    refreshes += 1;
    return Response.json({ status: 200, data: { access_token: token(refreshes) } });
  }
  if (path.endsWith("/auth/login")) {
    return Response.json({ status: 200, meta: { access_token: token(100) } });
  }
  if (path.endsWith("/v1/me/")) return Response.json(ME);
  return Response.json({ ok: true });
});

function setHint(on: boolean) {
  document.cookie = on ? "rz_session=1; path=/" : "rz_session=; path=/; max-age=0";
}

beforeEach(() => {
  calls = [];
  refreshes = 0;
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  resetBrowserSessionForTests();
  setAccessToken(null);
  setHint(false);
  fetchMock.mockClear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AuthProvider", () => {
  it("is anonymous without the hint cookie, with no request", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(await screen.findByText("anonymous:no user")).toBeInTheDocument();
    expect(calls).toEqual([]);
  });

  it("restores the session from the cookie once, even in StrictMode", async () => {
    setHint(true);
    render(
      <StrictMode>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </StrictMode>,
    );
    expect(screen.getByText("loading:no user")).toBeInTheDocument();
    expect(await screen.findByText("authenticated:ada")).toBeInTheDocument();
    expect(calls).toEqual(["POST /api/auth/app/v1/tokens/refresh", "GET /api/v1/me/"]);
    expect(getAccessToken()).toBe(token(1));
  });

  it("refreshes once on a 401 and retries with the new token", async () => {
    setHint(true);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await screen.findByText("authenticated:ada");
    // Pretend the refresh happened long ago, so the hook refreshes instead of just retrying.
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 60_000);

    let posts = 0;
    fetchMock.mockImplementationOnce(async (url: string, init?: RequestInit) => {
      posts += 1;
      calls.push(`${init?.method ?? "GET"} ${url}`);
      return Response.json({ detail: "Expired.", code: "not_authenticated" }, { status: 401 });
    });
    await act(async () => {
      await api.get("/v1/posts/");
    });
    expect(posts).toBe(1);
    expect(calls.slice(-3)).toEqual([
      "GET /api/v1/posts/",
      "POST /api/auth/app/v1/tokens/refresh",
      "GET /api/v1/posts/",
    ]);
    const retried = fetchMock.mock.calls.at(-1) as unknown as [string, RequestInit];
    expect(new Headers(retried[1].headers).get("authorization")).toBe(`Bearer ${token(2)}`);
  });

  it("logs in through the context", async () => {
    function LoginButton() {
      const { login } = useAuth();
      return <button onClick={() => void login("ada@example.test", "pw")}>log in</button>;
    }
    render(
      <AuthProvider>
        <Probe />
        <LoginButton />
      </AuthProvider>,
    );
    await screen.findByText("anonymous:no user");
    act(() => screen.getByRole("button", { name: "log in" }).click());
    await waitFor(() => expect(screen.getByText("authenticated:ada")).toBeInTheDocument());
    expect(getAccessToken()).toBe(token(100));
  });

  it("throws a clear error outside the provider", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow("useAuth() must be used inside <AuthProvider>");
  });
});
