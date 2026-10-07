import { expect, test } from "@playwright/test";
import { BANNER, PASSWORD, expectLoggedIn, logOut, signUp } from "./helpers";
import { waitForEmailLink } from "./mailbox";

/**
 * Part 2: the two email flows against the real stack, reading the emails Django writes to
 * backend/tmp/mail (EMAIL_PROVIDER=file). Every test signs up its own account.
 */

const NEW_PASSWORD = "a-brand-new-passphrase-77";

test("sign up → read the email → open the link → verified → New post is enabled", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const account = await signUp(page, "verify", { stay: true });

  // a4: where the link went, what is limited, and the resend countdown.
  await expect(page.getByRole("heading", { name: "Verify your email" })).toBeVisible();
  await expect(page.getByText(account.email)).toBeVisible();
  await expect(page.getByRole("button", { name: /Resend email \(\d+s\)/ })).toBeDisabled();

  await page.getByRole("link", { name: /Continue browsing read-only/ }).click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByText(BANNER)).toBeVisible();
  const rail = page.getByRole("complementary");
  const newPost = rail.getByRole("button", { name: "New post" });
  await expect(newPost).toHaveAttribute("aria-disabled", "true");
  // Playwright treats aria-disabled as "not enabled", but a person can still click it.
  await newPost.click({ force: true });
  await expect(page.getByText(/Verify your email to post\. Check your inbox/)).toBeVisible();

  // The link in the email: the page reads the key from the address and verifies it.
  const link = await waitForEmailLink(account.email, "verify-email");
  expect(link).toMatch(/^http:\/\/localhost:3000\/verify-email\/[^/]+$/);
  await page.goto(link);
  await expect(page.getByRole("heading", { name: "Your email is verified" })).toBeVisible();
  await page.getByRole("link", { name: /Start posting/ }).click();
  await expect(page).toHaveURL(/\/home$/);

  await expectLoggedIn(page, account.username);
  await expect(page.getByText(BANNER)).toHaveCount(0);
  await expect(rail.getByRole("button", { name: "New post" })).not.toHaveAttribute(
    "aria-disabled",
    "true",
  );

  // The link works once: a second visit is "already verified" for a signed-in verified user.
  await page.goto(link);
  await expect(page.getByRole("heading", { name: "Your email is already verified" })).toBeVisible();
});

test("forgot password → read the email → reset → logged in → log in with the new password", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const account = await signUp(page, "reset");
  await logOut(page);

  await page.goto("/login");
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await page.getByLabel("Email address").fill(account.email);
  await page.getByRole("button", { name: /Send reset link/ }).click();
  await expect(
    page.getByText(`If an account exists for ${account.email}, we've sent a link`),
  ).toBeVisible();

  const link = await waitForEmailLink(account.email, "reset-password");
  expect(link).toMatch(/^http:\/\/localhost:3000\/reset-password\/[0-9a-z-]+$/);
  await page.goto(link);
  await expect(page.getByRole("heading", { name: "Create new password" })).toBeVisible();

  await page.getByLabel("New password", { exact: true }).fill(NEW_PASSWORD);
  await page.getByLabel("Confirm new password").fill("something-else-entirely");
  await page.getByRole("button", { name: /Reset password & log in/ }).click();
  await expect(page.getByText("The passwords don't match.")).toBeVisible();

  await page.getByLabel("Confirm new password").fill(NEW_PASSWORD);
  await page.getByRole("button", { name: /Reset password & log in/ }).click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByText("Password changed. You're logged in.")).toBeVisible();
  await expectLoggedIn(page, account.username);

  // The link is used up.
  await page.goto(link);
  await expect(page.getByRole("heading", { name: "This link has expired" })).toBeVisible();

  await page.goto("/home");
  await logOut(page);
  await page.getByLabel("Email address").fill(account.email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /Log in/ }).click();
  await expect(page.getByText("That email and password don't match.")).toBeVisible();
  await page.getByLabel("Password", { exact: true }).fill(NEW_PASSWORD);
  await page.getByRole("button", { name: /Log in/ }).click();
  await expect(page).toHaveURL(/\/home$/);
  await expectLoggedIn(page, account.username);
});

test("an unknown address gets the same page and no email", async ({ page }) => {
  const ghost = `ghost-${Date.now().toString(36)}@example.test`;
  await page.goto("/forgot-password");
  await page.getByLabel("Email address").fill(ghost);
  await page.getByRole("button", { name: /Send reset link/ }).click();
  await expect(
    page.getByText(`If an account exists for ${ghost}, we've sent a link`),
  ).toBeVisible();
  await expect(waitForEmailLink(ghost, "reset-password", 2_000)).rejects.toThrow(
    /No reset-password email/,
  );
});

test("a dead reset link and a dead verification link show their expired states", async ({
  page,
}) => {
  await page.goto("/reset-password/0123456789abcdef0123456789abcdef-1abc-0fed1234");
  await expect(page.getByRole("heading", { name: "This link has expired" })).toBeVisible();
  await page.getByRole("link", { name: "Request a new link" }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);

  await page.goto("/verify-email/Mg%3A1vABcd%3Aabc-DEF_123");
  await expect(page.getByRole("heading", { name: "This link has expired" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Log in to send a new link" })).toHaveAttribute(
    "href",
    "/login?next=%2Fverify-email",
  );
});
