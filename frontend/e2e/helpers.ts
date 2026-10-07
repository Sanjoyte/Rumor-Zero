import { expect, type Page } from "@playwright/test";

/** Shared by the auth specs: every test signs up its own account. */
export const PASSWORD = "correct-horse-battery-42";
export const BANNER = "Verify your email to post, comment and report.";

export function newAccount(prefix: string) {
  const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  return { email: `${prefix}-${id}@example.test`, username: `${prefix}_${id}` };
}

/**
 * Sign up with Cloudflare's always-pass test key. A new account lands on /verify-email (Part 2);
 * unless `stay`, the helper continues browsing read-only, which shows the unverified banner.
 */
export async function signUp(page: Page, prefix = "e2e", { stay = false } = {}) {
  const account = newAccount(prefix);
  await page.goto("/signup");
  await page.getByLabel("Email address").fill(account.email);
  await page.getByLabel("Username").fill(account.username);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await expect(page.getByText(`Available: @${account.username}`)).toBeVisible();
  const submit = page.getByRole("button", { name: "Create account" });
  // The test widget solves itself; the button waits for its token.
  await expect(submit).toBeEnabled({ timeout: 30_000 });
  await submit.click();
  await expect(page).toHaveURL(/\/verify-email$/);
  if (!stay) {
    await page.getByRole("link", { name: /Continue browsing read-only/ }).click();
    await expect(page).toHaveURL(/\/home$/);
    await expect(page.getByText(BANNER)).toBeVisible();
  }
  return account;
}

export async function expectLoggedIn(page: Page, username: string) {
  const rail = page.getByRole("complementary");
  await expect(rail.getByText(`@${username}`, { exact: true }).first()).toBeVisible();
  await expect(rail.getByRole("link", { name: "Log in" })).toHaveCount(0);
}

export async function logOut(page: Page) {
  await page.getByRole("button", { name: "User menu" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
}
