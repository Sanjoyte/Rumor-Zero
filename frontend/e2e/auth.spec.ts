import { expect, test, type APIRequestContext } from "@playwright/test";
import { BANNER, PASSWORD, expectLoggedIn, signUp } from "./helpers";

/**
 * Part 1: sign up (Cloudflare's always-pass test key) → banner → cookies → staying logged in
 * (reloads, two tabs, two tabs at token expiry) → log out. Every test uses its own account. Since
 * Part 2 a new account lands on /verify-email first; `signUp` continues browsing read-only.
 */

const ORIGIN = "http://localhost:3000";

async function refreshWith(request: APIRequestContext, headers: Record<string, string>) {
  return request.post("/api/auth/app/v1/tokens/refresh", { headers, maxRedirects: 0 });
}

test("sign up, stay logged in across a reload, log out", async ({ page, context, request }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const account = await signUp(page);
  await expectLoggedIn(page, account.username);

  // The refresh token is only in the httpOnly cookie; the hint is the only readable one.
  const cookies = await context.cookies();
  const refresh = cookies.find((cookie) => cookie.name === "rz_refresh");
  const hint = cookies.find((cookie) => cookie.name === "rz_session");
  expect(refresh).toMatchObject({
    domain: "localhost",
    path: "/api/auth/",
    httpOnly: true,
    sameSite: "Lax",
  });
  expect(hint).toMatchObject({ value: "1", path: "/", httpOnly: false, sameSite: "Lax" });
  const browserView = await page.evaluate(() => ({
    cookie: document.cookie,
    local: Object.keys(localStorage),
    session: Object.keys(sessionStorage),
  }));
  expect(browserView).toEqual({ cookie: "rz_session=1", local: [], session: [] });

  await page.reload();
  await expectLoggedIn(page, account.username);
  await expect(page.getByText(BANNER)).toBeVisible();

  const oldRefresh = (await context.cookies()).find((c) => c.name === "rz_refresh")?.value;
  expect(oldRefresh).toBeTruthy();

  await page.getByRole("button", { name: "User menu" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await context.cookies()).map((cookie) => cookie.name)).not.toContain("rz_refresh");
  expect((await context.cookies()).map((cookie) => cookie.name)).not.toContain("rz_session");

  await page.goto("/home");
  await expect(page.getByRole("complementary").getByRole("link", { name: "Log in" })).toBeVisible();

  // The cookie the browser had is dead, and the CSRF guard needs the custom header.
  const dead = await refreshWith(request, {
    Origin: ORIGIN,
    "X-Requested-With": "rumor-zero",
    Cookie: `rz_refresh=${oldRefresh}`,
  });
  expect(dead.status()).toBe(400);
  const noHeader = await refreshWith(request, {
    Origin: ORIGIN,
    Cookie: `rz_refresh=${oldRefresh}`,
  });
  expect(noHeader.status()).toBe(403);
  expect(await noHeader.json()).toMatchObject({ errors: [{ code: "csrf_failed" }] });

  // A protected page asks you to log in, then brings you back.
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/login\?next=%2Fsettings$/);
  await page.getByLabel("Email address").fill(account.email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /Log in/ }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expectLoggedIn(page, account.username);
});

test("two tabs that load at once, then reload together, stay logged in", async ({ context }) => {
  const first = await context.newPage();
  const account = await signUp(first, "tabs");
  const second = await context.newPage();
  await Promise.all([first.goto("/home"), second.goto("/home")]);
  await Promise.all([
    expectLoggedIn(first, account.username),
    expectLoggedIn(second, account.username),
  ]);
  await Promise.all([first.reload(), second.reload()]);
  await Promise.all([
    expectLoggedIn(first, account.username),
    expectLoggedIn(second, account.username),
  ]);
});

test("two tabs open at token expiry both stay logged in", async ({ context }) => {
  await context.clock.install();
  const first = await context.newPage();
  const account = await signUp(first, "expiry");
  const second = await context.newPage();
  await second.goto("/home");
  await expectLoggedIn(second, account.username);

  // Jump past the scheduled refresh (60 s before the 15-minute expiry) in both tabs at once.
  const isRefresh = (response: { url(): string }) => response.url().endsWith("/tokens/refresh");
  const refreshed = Promise.all([
    first.waitForResponse(isRefresh),
    second.waitForResponse(isRefresh),
  ]);
  await context.clock.fastForward("14:30");
  const [a, b] = await refreshed;
  expect([a.status(), b.status()]).toEqual([200, 200]);

  await Promise.all([first.reload(), second.reload()]);
  await Promise.all([
    expectLoggedIn(first, account.username),
    expectLoggedIn(second, account.username),
  ]);
});
