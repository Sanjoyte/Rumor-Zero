import { describe, expect, it } from "vitest";
import { tokenClaims, tokenLifetimeSeconds } from "./jwt";
import { safeNextPath } from "./next-path";
import { isProtectedPath, loginRedirectFor } from "./route-guard";
import { hasSessionHint } from "./session-hint";

function segment(value: unknown): string {
  return btoa(JSON.stringify(value)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

describe("tokenClaims", () => {
  it("reads sub, iat and exp", () => {
    const token = `${segment({ alg: "HS256" })}.${segment({ sub: "u-1", iat: 100, exp: 1000, sid: "x" })}.sig`;
    expect(tokenClaims(token)).toEqual({ sub: "u-1", iat: 100, exp: 1000 });
    expect(tokenLifetimeSeconds({ sub: "u-1", iat: 100, exp: 1000 })).toBe(900);
  });

  it("decodes base64url payloads with non-ASCII text", () => {
    const payload = btoa(
      String.fromCharCode(...new TextEncoder().encode('{"sub":"ü?>","iat":1,"exp":2}')),
    )
      .replace(/=+$/, "")
      .replace(/\+/g, "-")
      .replace(/\//g, "_");
    expect(tokenClaims(`h.${payload}.s`)?.sub).toBe("ü?>");
  });

  it.each([
    "",
    "not-a-jwt",
    "a.b",
    "a.!!!.c",
    `h.${segment({ sub: 1, iat: 1, exp: 2 })}.s`,
    `h.${segment({ sub: "u", iat: "1", exp: 2 })}.s`,
    `h.${segment({ sub: "u", iat: 5, exp: 5 })}.s`,
    `h.${segment(null)}.s`,
  ])("returns null for %j", (token) => {
    expect(tokenClaims(token)).toBeNull();
  });
});

describe("hasSessionHint", () => {
  it.each([
    ["rz_session=1", true],
    ["a=1; rz_session=1; b=2", true],
    ["", false],
    ["rz_session=0", false],
    ["rz_session=", false],
    ["xrz_session=1", false],
  ])("%j → %s", (cookies, expected) => {
    expect(hasSessionHint(cookies)).toBe(expected);
  });
});

describe("safeNextPath", () => {
  const origin = "http://localhost:3000";

  it.each([
    ["/settings", "/settings"],
    ["/u/ada?tab=facts#top", "/u/ada?tab=facts#top"],
    ["/search?q=a%2Fb", "/search?q=a%2Fb"],
    ["/./notifications", "/notifications"],
    ["/home/../bookmarks", "/bookmarks"],
    ["/loginx", "/loginx"],
    // Encoded characters stay encoded in the path, so they can't leave the site.
    ["/%0a/evil", "/%0a/evil"],
    ["/%2F%2Fevil.com", "/%2F%2Fevil.com"],
  ])("keeps %j as %j", (raw, expected) => {
    expect(safeNextPath(raw, origin)).toBe(expected);
  });

  it.each([
    null,
    undefined,
    "",
    "settings",
    "//evil.com",
    "/\\evil.com",
    "/\\/evil.com",
    "/.//evil.com",
    "/..//evil.com",
    "https://evil.com/",
    "http://localhost:3000.evil.com/",
    "javascript:alert(1)",
    "/home\n",
    "/home\u0000",
    "/api/auth/logout/",
    "/api",
    "/login",
    "/login?next=/settings",
    "/signup",
    "/signup/",
  ])("rejects %j", (raw) => {
    expect(safeNextPath(raw, origin)).toBeNull();
  });
});

describe("route guard", () => {
  it.each([
    ["/settings", true],
    ["/settings/password", true],
    ["/notifications", true],
    ["/bookmarks", true],
    ["/home", false],
    ["/search", false],
    ["/u/ada", false],
    ["/settingsx", false],
  ])("%s protected: %s", (path, expected) => {
    expect(isProtectedPath(path)).toBe(expected);
  });

  it("builds the login URL with the page to come back to", () => {
    expect(loginRedirectFor("/settings?tab=a&b=1")).toBe(
      "/login?next=%2Fsettings%3Ftab%3Da%26b%3D1",
    );
  });
});
