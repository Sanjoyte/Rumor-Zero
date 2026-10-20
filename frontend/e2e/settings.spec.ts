import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";
import { logIn, logOut, marker, PASSWORD, seedAuthor } from "./helpers";

/**
 * Part 14: edit the profile, change the password, download your data, delete the account. Both
 * people are seeded (no sign-up: the suite is bounded by allauth's 20 sign-ups a minute).
 */

const NEW_PASSWORD = "a-brand-new-passphrase-77";

/** Post an opinion from /home through the composer. */
async function postOpinion(page: Page, text: string) {
  await page.goto("/home");
  await page.getByRole("complementary").getByRole("button", { name: "New post" }).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await dialog.getByRole("textbox", { name: "Post text" }).fill(text);
  await dialog.getByRole("radio", { name: "Opinion" }).click();
  await dialog.getByRole("button", { name: "Post opinion" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("article").filter({ hasText: text })).toHaveCount(1);
}

test("edit the profile, change the password, download your data", async ({ page }) => {
  const account = seedAuthor("sta");
  const claim = `Export me ${marker("st")}`;
  await logIn(page, account);
  await postOpinion(page, claim);

  // ----- the profile -----
  await page.goto("/settings");
  await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
  const newName = `${account.username}x`.slice(0, 30);
  await page.getByLabel("Display name").fill("Edited Name");
  await page.getByLabel("Username").fill(newName);
  await page.getByLabel("Bio").fill("A short bio\nwith two lines");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Profile saved.")).toBeVisible();
  await expect(page.getByRole("group", { name: "Unsaved changes" })).toHaveCount(0);
  // The rail follows the save, and the new profile is a real page.
  await expect(page.getByRole("complementary").getByText(`@${newName}`).first()).toBeVisible();
  const fresh = await page.goto(`/u/${newName}`);
  expect(fresh?.status()).toBe(200);
  await expect(page.getByText("A short bio")).toBeVisible();
  const old = await page.goto(`/u/${account.username}`);
  expect(old?.status()).toBe(404);

  // ----- the password -----
  await page.goto("/settings");
  await page.getByRole("button", { name: "Change password" }).click();
  const dialog = page.getByRole("dialog", { name: "Change password" });
  await dialog.getByLabel("Current password").fill(PASSWORD);
  await dialog.getByLabel("New password", { exact: true }).fill(NEW_PASSWORD);
  await dialog.getByLabel("Confirm new password").fill(NEW_PASSWORD);
  await dialog.getByRole("button", { name: "Change password" }).click();
  await expect(
    page.getByText("Password changed. Your other devices are signed out."),
  ).toBeVisible();
  await expect(dialog).toBeHidden();

  // ----- the export -----
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: /Download your data/ }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(
    new RegExp(`^rumor-zero-${newName}-\\d{4}-\\d{2}-\\d{2}\\.json$`),
  );
  const text = await readFile((await download.path())!, "utf8");
  const data = JSON.parse(text);
  expect(data.format).toBe("rumor-zero-export");
  expect(data.account.username).toBe(newName);
  expect(data.account.bio).toBe("A short bio\nwith two lines");
  expect(data.posts.map((post: { content: string }) => post.content)).toContain(claim);
  expect(text).not.toContain("search_vector");
  expect(text).not.toContain("pipeline_result");

  // The old password is dead, the new one works.
  await logOut(page);
  await page.getByLabel("Email address").fill(account.email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /Log in/ }).click();
  await expect(page.getByText("That email and password don't match.")).toBeVisible();
  await page.getByLabel("Password", { exact: true }).fill(NEW_PASSWORD);
  await page.getByRole("button", { name: /Log in/ }).click();
  await expect(page).toHaveURL(/\/home$/, { timeout: 30_000 });
});

test("delete the account: you land on /home signed out and can't log in again", async ({
  page,
}) => {
  const account = seedAuthor("std");
  const claim = `Delete me ${marker("sd")}`;
  await logIn(page, account);
  await postOpinion(page, claim);

  await page.goto("/settings");
  await page.getByRole("button", { name: "Delete account…" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete your account?" });
  const confirm = dialog.getByRole("button", { name: "Delete account" });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel("Your password").fill("not-my-password-1");
  await confirm.click();
  await expect(dialog.getByText("That password is not right.")).toBeVisible();

  await dialog.getByLabel("Your password").fill(PASSWORD);
  await confirm.click();
  await expect(page).toHaveURL(/\/home$/, { timeout: 30_000 });
  await expect(page.getByText("Your account has been deleted.")).toBeVisible();
  await expect(page.getByRole("complementary").getByRole("link", { name: "Log in" })).toBeVisible();
  await expect(page.getByText(claim)).toHaveCount(0);

  // Its profile is gone, and the credentials no longer open anything.
  const profile = await page.goto(`/u/${account.username}`);
  expect(profile?.status()).toBe(404);
  await page.goto("/login");
  await page.getByLabel("Email address").fill(account.email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /Log in/ }).click();
  await expect(page.getByText("That email and password don't match.")).toBeVisible();
});
