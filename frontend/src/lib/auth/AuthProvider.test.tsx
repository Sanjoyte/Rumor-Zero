import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import { AuthProvider, useAuth } from "./AuthProvider";
import { setAccessToken } from "./token-store";

function Probe() {
  const { status, user } = useAuth();
  return <p>{`${status}:${user === null ? "no user" : user.username}`}</p>;
}

afterEach(() => {
  setAccessToken(null);
  vi.unstubAllGlobals();
});

describe("AuthProvider", () => {
  it("starts anonymous (Part 1 adds sign-in)", () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(screen.getByText("anonymous:no user")).toBeInTheDocument();
  });

  it("gives the API client the in-memory token, and a 401 stays final", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response('{"detail":"No.","code":"not_authenticated"}', {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    setAccessToken("access-1");
    await expect(api.get("/v1/me/")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(init[1].headers).get("authorization")).toBe("Bearer access-1");
  });

  it("throws a clear error outside the provider", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow("useAuth() must be used inside <AuthProvider>");
  });
});
