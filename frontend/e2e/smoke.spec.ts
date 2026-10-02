import { expect, test } from "@playwright/test";

/**
 * Part 0C smoke test: the relay reaches Django, the layouts carry the logo, and the app shell
 * switches between rail, icon dock and bottom bar, all logged out (auth.spec.ts logs in).
 */

test("the relay forwards /api/health/ to Django", async ({ request }) => {
  const response = await request.get("/api/health/", { maxRedirects: 0 });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ status: "ok" });
});

test("the landing page shows the logo and the footer", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("Rumor Zero");
  await expect(page.getByRole("banner").getByRole("img", { name: "Rumor Zero" })).toBeVisible();
  await expect(page.getByRole("contentinfo").getByText("© 2026 Rumor Zero")).toBeVisible();
  await expect(page.getByRole("link", { name: "How it works" })).toHaveAttribute(
    "href",
    "/how-it-works",
  );
});

test("page URLs drop a trailing slash", async ({ page }) => {
  await page.goto("/home/");
  await expect(page).toHaveURL(/\/home$/);
  await expect(page).toHaveTitle("Home · Rumor Zero");
});

test("the app shell has the full rail at 1280px", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/home");
  const rail = page.getByRole("complementary");
  await expect(rail).toBeVisible();
  expect((await rail.boundingBox())?.width).toBe(256);
  const home = rail.getByRole("link", { name: "Home" });
  await expect(home).toHaveAttribute("aria-current", "page");
  await expect(home.getByText("Home", { exact: true })).toBeVisible();
  await expect(rail.getByRole("link", { name: "Rumor Zero" })).toBeVisible();
  await expect(page.getByRole("search")).toBeVisible();
});

test("the app shell has the icon dock at 1024px", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.goto("/home");
  const rail = page.getByRole("complementary");
  expect((await rail.boundingBox())?.width).toBe(64);
  const home = rail.getByRole("link", { name: "Home" });
  await expect(home).toHaveAttribute("aria-current", "page");
  // The label is visually hidden but still names the link.
  expect(
    (await home.getByText("Home", { exact: true }).boundingBox())?.width ?? 0,
  ).toBeLessThanOrEqual(1);
  await page.getByRole("searchbox", { name: "Search" }).fill("vaccines");
  await page.getByRole("searchbox", { name: "Search" }).press("Enter");
  await expect(page).toHaveURL(/\/search\?q=vaccines$/);
});

test("the app shell has a top bar and bottom bar at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/home");
  await expect(page.getByRole("complementary")).toBeHidden();
  const bottom = page.getByRole("navigation", { name: "Main" });
  await expect(bottom).toBeVisible();
  expect((await bottom.boundingBox())?.y).toBe(844 - 64);
  await expect(bottom.getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
  await expect(bottom.getByRole("link", { name: "Log in" })).toBeVisible();
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scrollWidth).toBe(390);
});

test("the auth card shows the large logo", async ({ page }) => {
  await page.goto("/login");
  await expect(page).toHaveTitle("Log in · Rumor Zero");
  const logo = page.getByRole("main").getByRole("img", { name: "Rumor Zero" });
  await expect(logo).toBeVisible();
  // Preflight sets `height: auto`, so the rounded width decides the last fraction of a pixel.
  expect((await logo.boundingBox())?.height).toBeCloseTo(48, 0);
});

test("an unknown URL shows the 404 page with the logo", async ({ page }) => {
  const response = await page.goto("/no-such-page");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Rumor Zero" })).toBeVisible();
});
