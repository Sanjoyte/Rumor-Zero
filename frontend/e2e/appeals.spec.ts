import { expect, test, type Page } from "@playwright/test";
import { logIn, marker, moderate, seedAuthor, setPostState } from "./helpers";

/**
 * Part 11: asking for another look at a FALSE label and at a removal, against the real stack.
 * The authors are seeded (no sign-up: the suite is at 16 of allauth's 20 a minute), and the
 * moderators' decisions go through the backend's own services, as the admin does.
 */

const newPost = (page: Page) =>
  page.getByRole("complementary").getByRole("button", { name: "New post" });

/** Post a fact through the composer from /home, open its page and return the post's id. */
async function postFact(page: Page, text: string) {
  await newPost(page).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await dialog.getByRole("textbox", { name: "Post text" }).fill(text);
  await dialog.getByRole("radio", { name: "Fact" }).click();
  await dialog.getByRole("button", { name: "Post fact, will be checked" }).click();
  await expect(dialog).toBeHidden();
  const card = page.getByRole("article").filter({ hasText: text });
  await expect(card).toHaveCount(1);
  await card.getByRole("link", { name: new RegExp(text) }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  return page.url().split("/p/")[1];
}

test("a FALSE label can be appealed once, goes under review, and a reversal shows the author", async ({
  page,
}) => {
  const author = seedAuthor("apl");
  await logIn(page, author);
  const claim = `Label ${marker("lb")}`;
  const postId = await postFact(page, claim);

  setPostState(postId, "verified_false");
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(claim);
  await expect(page.getByText("FALSE 90%").first()).toBeVisible();

  await page.getByRole("button", { name: "Request another look" }).click();
  const dialog = page.getByRole("dialog", { name: "Request another look" });
  await expect(dialog.getByText("Your post is labelled FALSE.")).toBeVisible();
  await dialog
    .getByRole("textbox", { name: "Why should we look again?" })
    .fill("The source was updated.");
  await dialog.getByRole("button", { name: "Send request" }).click();
  await expect(dialog).toBeHidden();

  // At once: UNDER REVIEW, the chip, and no second request.
  await expect(page.getByText("Request sent. A moderator will take another look.")).toBeVisible();
  await expect(page.getByText("UNDER REVIEW").first()).toBeVisible();
  await expect(page.getByText("APPEAL PENDING")).toBeVisible();
  await expect(page.getByRole("button", { name: "Request another look" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("APPEAL PENDING")).toBeVisible();
  await expect(page.getByRole("button", { name: "Request another look" })).toHaveCount(0);

  // A moderator who didn't make the first decision reverses it.
  moderate(postId, "mark_verified", "Rechecked against the filing");
  await page.reload();
  await expect(page.getByText("VERIFIED · REVIEWED").first()).toBeVisible();
  await expect(page.getByText("A moderator reversed the decision.")).toBeVisible();
  await expect(page.getByText("APPEAL PENDING")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Request another look" })).toHaveCount(0);
});

test("a removed post shows its author the reason and the button, on the page and on their profile", async ({
  page,
  browser,
}) => {
  const author = seedAuthor("apr");
  await logIn(page, author);
  const claim = `Removal ${marker("rm")}`;
  const postId = await postFact(page, claim);

  moderate(postId, "remove_post", "Personal attack");
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(claim);
  await expect(page.getByText("Only you can see this text.")).toBeVisible();
  await expect(page.getByText("Reason given: Personal attack")).toBeVisible();
  await expect(page.getByRole("button", { name: "Request another look" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Verdict" })).toHaveCount(0);

  // Your own profile lists it; everyone else's view of it is a tombstone with no text.
  await page.goto(`/u/${author.username}`);
  const card = page.getByRole("article").filter({ hasText: claim });
  await expect(card.getByText("Reason given: Personal attack")).toBeVisible();
  const visitor = await browser.newContext();
  const visitorPage = await visitor.newPage();
  await visitorPage.goto(`/u/${author.username}`);
  await expect(visitorPage.getByText(claim)).toHaveCount(0);
  await visitor.close();

  // Ask from the profile card: the chip replaces the button.
  await card.getByRole("button", { name: "Request another look" }).click();
  const dialog = page.getByRole("dialog", { name: "Request another look" });
  await expect(dialog.getByText("A moderator removed your post.")).toBeVisible();
  await expect(dialog.getByText("Reason given: Personal attack")).toBeVisible();
  await dialog.getByRole("button", { name: "Send request" }).click();
  await expect(dialog).toBeHidden();
  await expect(card.getByText("APPEAL PENDING")).toBeVisible();
  await expect(card.getByRole("button", { name: "Request another look" })).toHaveCount(0);

  // The moderator keeps it removed: the author is told so.
  moderate(postId, "keep_removed");
  await page.reload();
  await expect(
    page
      .getByRole("article")
      .filter({ hasText: claim })
      .getByText(/the post stays removed/),
  ).toBeVisible();
  await page.goto(`/p/${postId}`);
  await expect(page.getByText(/the post stays removed/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Request another look" })).toHaveCount(0);
});
