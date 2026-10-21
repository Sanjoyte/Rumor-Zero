import { expect, test } from "@playwright/test";

/**
 * Part 15: landing → how verification works → sign up, all logged out. Read-only: it creates
 * nothing, so it can run against a shared server.
 */

test("landing, how it works, credibility anchor, sign up", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("Rumor Zero");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "opinions are labelled, and facts are checked",
  );
  await expect(page.getByRole("link", { name: "Create account" })).toHaveAttribute(
    "href",
    "/signup",
  );
  // The preview loads in the browser: cards, or the empty notice on a fresh database.
  await expect(page.getByRole("article").first().or(page.getByText("No posts yet"))).toBeVisible();

  await page.getByRole("banner").getByRole("link", { name: "How it works" }).click();
  await expect(page).toHaveURL(/\/how-it-works$/);
  await expect(page).toHaveTitle("How verification works · Rumor Zero");
  await expect(page.getByRole("table", { name: /Post labels/ })).toBeVisible();
  await expect(
    page.getByRole("table", { name: /Post labels/ }).getByText(/EMERGENCY/),
  ).toBeVisible();

  await page.goto("/how-it-works#credibility");
  await expect(
    page.getByRole("heading", { name: "How your credibility score is calculated" }),
  ).toBeInViewport();

  await page.getByRole("banner").getByRole("link", { name: "Sign up" }).click();
  await expect(page).toHaveURL(/\/signup$/);
  await expect(page).toHaveTitle("Sign up · Rumor Zero");
});

test("privacy, terms and the 404 page", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page).toHaveTitle("Privacy · Rumor Zero");
  await expect(page.getByText("Needs legal review")).toBeVisible();
  await page.getByRole("contentinfo").getByRole("link", { name: "Terms" }).click();
  await expect(page).toHaveTitle("Terms · Rumor Zero");
  await expect(page.getByRole("heading", { name: "Credibility score" })).toBeVisible();

  const response = await page.goto("/no-such-page");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});
