import { expect, test, type Page } from "@playwright/test";
import { marker, processPost, setPostState, signUpVerified } from "./helpers";

/**
 * Part 5: a post's own page, sharing, the author's delete and live badges, against the real stack.
 * The feed is shared by every parallel worker, so each test finds its post by a marker in its text.
 */

const newPost = (page: Page) =>
  page.getByRole("complementary").getByRole("button", { name: "New post" });

/** Post through the composer from /home and return the card. */
async function post(page: Page, type: "Fact" | "Opinion", text: string, sources: string[] = []) {
  await newPost(page).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await dialog.getByRole("textbox", { name: "Post text" }).fill(text);
  await dialog.getByRole("radio", { name: type }).click();
  for (const [index, source] of sources.entries()) {
    if (index > 0) await dialog.getByRole("button", { name: "Add another source" }).click();
    await dialog.getByRole("textbox", { name: `Source ${index + 1}` }).fill(source);
  }
  await dialog
    .getByRole("button", { name: type === "Fact" ? "Post fact, will be checked" : "Post opinion" })
    .click();
  await expect(dialog).toBeHidden();
  const card = page.getByRole("article").filter({ hasText: text });
  await expect(card).toHaveCount(1);
  return card;
}

/** Open a card's own page and return the post's id from the address. */
async function openFrom(page: Page, text: string) {
  await page
    .getByRole("article")
    .filter({ hasText: text })
    .getByRole("link", { name: new RegExp(text) })
    .click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  return page.url().split("/p/")[1];
}

test("a fact: open it from its card, read every source, copy the link, and a crawler gets the claim and the tags", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await signUpVerified(page, "detail");
  const id = marker("fact");
  const doi = `10.1000/rz-${id}`;
  const claim = `Claim ${id}`;
  await post(page, "Fact", claim, [`doi:${doi}`, `https://Example.org/${id}`]);

  const postId = await openFrom(page, claim);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(claim);
  await expect(page.getByText("CHECKING FACTS…").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Verdict" })).toBeVisible();

  // Every source, numbered in the order entered, with its full value and an open link.
  await expect(page.getByRole("heading", { name: "Sources (2)" })).toBeVisible();
  const items = page.getByRole("listitem").filter({ hasText: /^0[12]/ });
  await expect(items).toHaveCount(2);
  await expect(items.nth(0)).toContainText(doi);
  await expect(items.nth(1)).toContainText(`https://example.org/${id}`);
  const open = page.getByRole("link", { name: "Open source 01 in a new tab" });
  await expect(open).toHaveAttribute("href", `https://doi.org/${doi}`);
  await expect(open).toHaveAttribute("rel", "nofollow ugc noopener noreferrer");

  // The author gets Delete; Copy link puts this site's address on the clipboard.
  await expect(page.getByRole("button", { name: "Delete" })).toBeVisible();
  await page.getByRole("button", { name: "Copy link" }).click();
  await expect(page.getByText("Link copied.")).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toBe(`http://localhost:3000/p/${postId}`);

  // What a link preview or a search crawler sees: no cookies, no script, just the HTML.
  const response = await request.get(`/p/${postId}`);
  expect(response.status()).toBe(200);
  const html = await response.text();
  expect(html).toContain(claim);
  expect(html).toContain(`<title>${claim} · Rumor Zero</title>`);
  expect(html).toContain('content="Fact · CHECKING FACTS…"');
  expect(html).toMatch(new RegExp(`property="og:title" content="${claim} · Rumor Zero"`));
  expect(html).toMatch(
    /property="og:image" content="http:\/\/localhost:3000\/opengraph-image\.png/,
  );
  expect(html).toMatch(/name="twitter:image" content="http:\/\/localhost:3000\/twitter-image\.png/);
  expect(html).toContain(`rel="canonical" href="http://localhost:3000/p/${postId}"`);
  expect(html).not.toContain('content="noindex');

  // The card's "+1 more" goes to the same page, at the sources.
  await page.goto("/home");
  const card = page.getByRole("article").filter({ hasText: claim });
  await card.getByRole("link", { name: "+1 more" }).click();
  await expect(page).toHaveURL(new RegExp(`/p/${postId}#sources$`));
  await expect(page.getByRole("heading", { name: "Sources (2)" })).toBeInViewport();
});

test("the author deletes a post: gone from Recent, 404 for everyone, with a toast", async ({
  page,
  browser,
  request,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await signUpVerified(page, "delete");
  const id = marker("op");
  const text = `I think ${id}`;
  await post(page, "Opinion", text);
  const postId = await openFrom(page, text);
  await expect(page.getByText("Opinions aren't fact-checked.")).toBeVisible();

  // Cancel changes nothing.
  await page.getByRole("button", { name: "Delete" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete this post?" });
  await expect(dialog.getByText(/can't be undone/)).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).toBeHidden();
  expect((await request.get(`/p/${postId}`)).status()).toBe(200);

  await page.getByRole("button", { name: "Delete" }).click();
  await page
    .getByRole("dialog", { name: "Delete this post?" })
    .getByRole("button", { name: "Delete post" })
    .click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByText("Post deleted.")).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: id })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("article").filter({ hasText: id })).toHaveCount(0);

  // The page is a 404, to a crawler and to the author alike; the API says so too.
  expect((await request.get(`/p/${postId}`)).status()).toBe(404);
  await page.goto(`/p/${postId}`);
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  const visitor = await browser.newContext();
  const visitorPage = await visitor.newPage();
  const apiResponse = await visitorPage.request.get(`/api/v1/posts/${postId}/`);
  expect(apiResponse.status()).toBe(404);
  expect((await apiResponse.json()).code).toBe("not_found");
  await visitor.close();
});

test("a #true fact is checked by the pipeline and its badge turns VERIFIED by itself, on the feed and on its page", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1280, height: 900 });
  await signUpVerified(page, "live");
  const id = marker("live");
  const claim = `Claim ${id} #true`;
  const card = await post(page, "Fact", claim);
  await expect(card.getByText("CHECKING FACTS…")).toBeVisible();

  // The page for the same post, open in a second tab of the same browser.
  const second = await page.context().newPage();
  await second.goto("/home");
  const postId = await openFrom(second, claim);
  await expect(second.getByText("CHECKING FACTS…").first()).toBeVisible();

  // The pipeline checks the post underneath (Part 9), as the inline kick does after a post commits.
  const checked = processPost(postId);
  expect(
    checked.status,
    `the stub gives #true 95%; the E2E backend's confidence_threshold is ${checked.threshold}`,
  ).toBe("verified_true");

  // Part 5's polling picks the verdict up on both pages.
  await expect(card.getByText("VERIFIED 95%")).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText("CHECKING FACTS…")).toHaveCount(0);
  await expect(second.getByText("VERIFIED 95%").first()).toBeVisible({ timeout: 30_000 });
  await expect(second.getByText("Checked automatically · 95% confidence")).toBeVisible();
  await expect(second.getByText("CHECKING FACTS…")).toHaveCount(0);
});

test("a removed post: a tombstone for the public, the full post for its author", async ({
  page,
  browser,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await signUpVerified(page, "removed");
  const id = marker("rm");
  const claim = `Claim ${id}`;
  await post(page, "Fact", claim);
  const postId = await openFrom(page, claim);

  setPostState(postId, "removed");

  const visitor = await browser.newContext();
  const visitorPage = await visitor.newPage();
  await visitorPage.goto(`/p/${postId}`);
  await expect(visitorPage.getByText("This post was removed by a moderator.")).toBeVisible();
  await expect(visitorPage.getByText(claim)).toHaveCount(0);
  const api = await (await visitorPage.request.get(`/api/v1/posts/${postId}/`)).json();
  expect(api).toMatchObject({ status: "removed", content: "", sources: [] });
  const html = await (await visitorPage.request.get(`/p/${postId}`)).text();
  expect(html).not.toContain(claim);
  expect(html).toContain("<title>Removed post · Rumor Zero</title>");
  expect(html).toMatch(/name="robots" content="noindex/);
  await visitor.close();

  // The author still sees their own text, marked as removed.
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(claim);
  await expect(page.getByText(/Only you can see this text/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Verdict" })).toHaveCount(0);
  // And it is gone from Recent.
  await page.goto("/home");
  await expect(page.getByRole("button", { name: /What do you want to say/ })).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: claim })).toHaveCount(0);
});
