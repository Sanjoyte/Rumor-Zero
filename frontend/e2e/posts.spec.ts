import { expect, test, type Page } from "@playwright/test";
import { BANNER, marker, signUp, signUpVerified } from "./helpers";

/**
 * Part 4: the composer and the Recent feed against the real stack. Every test signs up its own
 * account, and the feed is shared by every parallel worker, so each test finds its post by a
 * marker that is in its text only. The fact allowance comes from the developer's own settings, so
 * no test assumes it is 10: they compare the number before and after.
 */

const newPost = (page: Page) =>
  page.getByRole("complementary").getByRole("button", { name: "New post" });

async function openComposer(page: Page) {
  await newPost(page).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await expect(dialog).toBeVisible();
  return dialog;
}

/** "7/10 fact posts left" → { left: 7, limit: 10 }. */
async function readAllowance(page: Page) {
  const dialog = page.getByRole("dialog", { name: "New post" });
  const line = dialog.getByText(/\d+\/\d+\s+fact posts left/);
  await expect(line).toBeVisible();
  const [, left, limit] = /(\d+)\/(\d+)/.exec((await line.textContent()) ?? "")!;
  return { left: Number(left), limit: Number(limit) };
}

test("post a fact with a DOI and a URL → CHECKING FACTS… and the source line, for everyone", async ({
  page,
  browser,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await signUpVerified(page, "post");
  const id = marker("fact");
  const doi = `10.1000/rz-${id}`;

  const dialog = await openComposer(page);
  const before = await readAllowance(page);
  expect(before.left).toBeGreaterThan(0);

  await dialog.getByRole("textbox", { name: "Post text" }).fill(`Claim ${id}`);
  // The type has no default: choosing it is part of posting.
  await dialog.getByRole("radio", { name: "Fact" }).click();
  await dialog.getByRole("textbox", { name: "Source 1" }).fill(`doi:${doi}`);
  await dialog.getByRole("button", { name: "Add another source" }).click();
  await dialog.getByRole("textbox", { name: "Source 2" }).fill(`https://Example.org/${id}`);
  await dialog.getByRole("button", { name: "Post fact, will be checked" }).click();

  // Insert on success: the composer closes and the post is on top of Recent.
  await expect(dialog).toBeHidden();
  await expect(page.getByText("Posted. Checking the facts…")).toBeVisible();
  const card = page.getByRole("article").filter({ hasText: id });
  await expect(card).toHaveCount(1);
  await expect(card.getByText("CHECKING FACTS…")).toBeVisible();
  await expect(card.getByText("FACT", { exact: true })).toBeVisible();
  await expect(card.getByText(`doi.org/${doi}`)).toBeVisible();
  await expect(card.getByText("+1 more")).toBeVisible();
  const link = card.getByRole("link", { name: new RegExp(`doi\\.org/${doi}`) });
  await expect(link).toHaveAttribute("href", `https://doi.org/${doi}`);
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", "nofollow ugc noopener noreferrer");

  // The allowance went down by one (a fresh composer: the draft was cleared by the post).
  const reopened = await openComposer(page);
  await expect(reopened.getByRole("textbox", { name: "Post text" })).toHaveValue("");
  const after = await readAllowance(page);
  expect(after).toEqual({ left: before.left - 1, limit: before.limit });
  await page.keyboard.press("Escape");

  // Reload: the post comes back from the server (the GET path), still checking.
  await page.reload();
  const reloaded = page.getByRole("article").filter({ hasText: id });
  await expect(reloaded.getByText("CHECKING FACTS…")).toBeVisible();
  await expect(reloaded.getByText(`doi.org/${doi}`)).toBeVisible();

  // Recent is public: a visitor with no account sees it too.
  const visitor = await browser.newContext();
  const visitorPage = await visitor.newPage();
  await visitorPage.goto("/home");
  const seen = visitorPage.getByRole("article").filter({ hasText: id });
  await expect(seen.getByText("CHECKING FACTS…")).toBeVisible();
  await expect(visitorPage.getByRole("link", { name: "Log in to post" })).toBeVisible();
  await visitor.close();
});

test("post an opinion → OPINION in italic serif, no status badge and no source line", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await signUpVerified(page, "opinion");
  const id = marker("op");

  // From the card on /home this time (the same composer as the rail's button).
  await page.getByRole("button", { name: /What do you want to say/ }).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await dialog.getByRole("textbox", { name: "Post text" }).fill(`I think ${id}`);
  await dialog.getByRole("radio", { name: "Opinion" }).click();
  await expect(dialog.getByRole("textbox", { name: /^Source/ })).toHaveCount(0);
  await dialog.getByRole("button", { name: "Post opinion" }).click();

  await expect(dialog).toBeHidden();
  await expect(page.getByText("Posted.", { exact: true })).toBeVisible();
  const card = page.getByRole("article").filter({ hasText: id });
  await expect(card.getByText("OPINION", { exact: true })).toBeVisible();
  await expect(card.getByRole("blockquote")).toHaveClass(/italic/);
  await expect(card.getByText("CHECKING FACTS…")).toHaveCount(0);
  // Part 5: the claim is the card's one link, to the post's own page.
  await expect(card.getByRole("link")).toHaveCount(1);
  await expect(card.getByRole("link")).toHaveAttribute("href", /^\/p\/[0-9a-f-]{36}$/);
});

test("the composer blocks a bad post on the page, before anything is sent", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await signUpVerified(page, "invalid");
  let posted = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/posts/")) posted += 1;
  });
  const dialog = await openComposer(page);

  // Nothing typed, nothing chosen.
  await dialog.getByRole("button", { name: /^Post/ }).click();
  await expect(dialog.getByText("Write something first.")).toBeVisible();
  await expect(dialog.getByText("Choose Opinion or Fact.")).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "Post text" })).toBeFocused();

  // A fact with a source the server would refuse.
  await dialog.getByRole("textbox", { name: "Post text" }).fill("A claim");
  await dialog.getByRole("radio", { name: "Fact" }).click();
  await dialog.getByRole("textbox", { name: "Source 1" }).fill("javascript:alert(1)");
  await dialog.getByRole("button", { name: "Post fact, will be checked" }).click();
  await expect(dialog.getByText(/starts with https:\/\//)).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "Source 1" })).toBeFocused();

  // Over 500 characters.
  await dialog.getByRole("radio", { name: "Opinion" }).click();
  await dialog.getByRole("textbox", { name: "Post text" }).fill("x".repeat(501));
  await expect(dialog.getByText("501 / 500 characters")).toBeVisible();
  await dialog.getByRole("button", { name: "Post opinion" }).click();
  await expect(dialog.getByText("Keep it to 500 characters.")).toBeVisible();

  expect(posted).toBe(0);
  // Closing keeps what was typed.
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await newPost(page).click();
  await expect(page.getByRole("textbox", { name: "Post text" })).toHaveValue("x".repeat(501));
});

test("an unverified user can read the feed but not post", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await signUp(page, "unverified"); // lands on /home, banner showing
  await expect(page.getByText(BANNER)).toBeVisible();
  const trigger = page.getByRole("button", { name: /What do you want to say/ });
  await expect(trigger).toHaveAttribute("aria-disabled", "true");
  // Playwright treats aria-disabled as "not enabled", but a person can still click it.
  await trigger.click({ force: true });
  await expect(page.getByText(/Verify your email to post\. Check your inbox/)).toBeVisible();
  await expect(page.getByRole("dialog", { name: "New post" })).toBeHidden();
  // The feed still loads for them.
  await expect(page.getByRole("tab", { name: "Recent" })).toHaveAttribute("aria-selected", "true");
});

test("the composer fits a phone: no horizontal scroll, source rows usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signUpVerified(page, "phone");
  await page.getByRole("button", { name: "New post" }).last().click(); // the bottom tab
  const dialog = page.getByRole("dialog", { name: "New post" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("radio", { name: "Fact" }).click();
  for (let n = 2; n <= 5; n += 1) {
    await dialog.getByRole("button", { name: "Add another source" }).click();
    await expect(dialog.getByRole("textbox", { name: `Source ${n}` })).toBeVisible();
  }
  await expect(dialog.getByRole("button", { name: "Add another source" })).toHaveCount(0);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBe(0);
});
