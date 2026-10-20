import { expect, test, type Page } from "@playwright/test";
import { logIn, marker, seedAuthor } from "./helpers";

/**
 * Part 13: someone likes and comments on your post; you see the badge, the items, and the count
 * go down as you read them. Both people are seeded (no sign-up: the suite is at 16 of allauth's
 * 20 a minute). The 30 s poll is never waited for: the badge shows on load, and a visibility
 * change makes the page ask at once.
 */

const newPost = (page: Page) =>
  page.getByRole("complementary").getByRole("button", { name: "New post" });

/** Post an opinion from /home and return its id. */
async function postOpinion(page: Page, text: string) {
  await newPost(page).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await dialog.getByRole("textbox", { name: "Post text" }).fill(text);
  await dialog.getByRole("radio", { name: "Opinion" }).click();
  await dialog.getByRole("button", { name: "Post opinion" }).click();
  await expect(dialog).toBeHidden();
  const card = page.getByRole("article").filter({ hasText: text });
  await expect(card).toHaveCount(1);
  await card.getByRole("link", { name: new RegExp(text) }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  return page.url().split("/p/")[1];
}

const railLink = (page: Page, name: string | RegExp) =>
  page.getByRole("complementary").getByRole("link", { name });

test("B likes and comments on A's post: A sees the badge, the items, and reads them", async ({
  page,
  browser,
}) => {
  const a = seedAuthor("nta");
  const b = seedAuthor("ntb");
  await logIn(page, a);
  const claim = `Notify ${marker("nt")}`;
  const postId = await postOpinion(page, claim);

  // Your own like says nothing to you.
  await page.getByRole("button", { name: /^Like/ }).first().click();
  await expect(page.getByRole("button", { name: /^Like/ }).first()).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.goto("/notifications");
  await expect(page.getByText("Nothing yet")).toBeVisible();
  await expect(railLink(page, "Notifications")).toBeVisible();
  await page.goto("/home");

  // B likes and comments in another browser.
  const other = await browser.newContext();
  const bobs = await other.newPage();
  await logIn(bobs, b);
  await bobs.goto(`/p/${postId}`);
  await bobs.getByRole("button", { name: /^Like/ }).first().click();
  await expect(bobs.getByRole("button", { name: /^Like/ }).first()).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  const box = bobs.getByRole("textbox", { name: "Add a comment" });
  await box.fill("Good point here");
  await box.press("Control+Enter");
  await expect(bobs.getByRole("heading", { name: "Comments (1)" })).toBeVisible();

  // A: the page asks again when it comes back to the screen.
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(railLink(page, "Notifications, 2 unread")).toBeVisible({ timeout: 15_000 });

  await railLink(page, /^Notifications/).click();
  await expect(page).toHaveURL(/\/notifications$/);
  await expect(page.getByText("2 unread")).toBeVisible();
  const items = page.getByRole("article");
  await expect(items).toHaveCount(2);
  await expect(items.filter({ hasText: "liked your post" })).toHaveCount(1);
  const comment = items.filter({ hasText: "commented on your post" });
  await expect(comment).toContainText("Good point here");
  await expect(comment).toContainText(claim);

  // Opening one reads it and goes to the post; the count falls.
  await items.filter({ hasText: "liked your post" }).getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/p/${postId}$`));
  await expect(railLink(page, "Notifications, 1 unread")).toBeVisible();

  // After a reload the server agrees.
  await page.goto("/notifications");
  await expect(page.getByText("1 unread")).toBeVisible();
  await expect(page.getByText("Unread", { exact: true })).toHaveCount(1);

  // Mark all as read.
  await page.getByRole("button", { name: "Mark all as read" }).click();
  await expect(page.getByText("1 unread")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Mark all as read" })).toHaveCount(0);
  await expect(page.getByText("Unread", { exact: true })).toHaveCount(0);
  await expect(railLink(page, "Notifications")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("article")).toHaveCount(2);
  await expect(page.getByText("Unread", { exact: true })).toHaveCount(0);
  await expect(railLink(page, "Notifications")).toBeVisible();

  await other.close();
});

test("a visitor is sent to log in", async ({ page }) => {
  await page.goto("/notifications");
  await expect(page).toHaveURL(/\/login\?next=%2Fnotifications$/);
});
