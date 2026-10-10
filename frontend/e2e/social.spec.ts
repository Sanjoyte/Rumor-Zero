import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { marker, seedPost, setPostState, signUpVerified } from "./helpers";

/**
 * Two people, signed up once for the whole file: allauth limits sign-ups to 20 a minute per
 * address and the rest of the suite already uses most of that. The tests run in order and each
 * leaves the follow between the two as it found it (not following).
 */
test.describe.configure({ mode: "serial" });

interface Person {
  context: BrowserContext;
  page: Page;
  username: string;
}
let fan: Person;
let star: Person;

test.beforeAll(async ({ browser }) => {
  test.setTimeout(120_000);
  async function newPerson(prefix: string): Promise<Person> {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    const { username } = await signUpVerified(page, prefix);
    return { context, page, username };
  }
  fan = await newPerson("fan");
  star = await newPerson("star");
});

test.afterAll(async () => {
  await fan?.context.close();
  await star?.context.close();
});

// `next dev` compiles a route the first time it is visited, which can take several seconds when
// the whole suite runs in parallel: assertions right after a navigation to a new route wait longer.
const NAVIGATION = { timeout: 20_000 };

async function postOpinion(page: Page, text: string) {
  await page.goto("/home");
  await page.getByRole("button", { name: /What do you want to say/ }).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await dialog.getByRole("textbox", { name: "Post text" }).fill(text);
  await dialog.getByRole("radio", { name: "Opinion" }).click();
  await dialog.getByRole("button", { name: "Post opinion" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText("Posted.", { exact: true })).toBeVisible();
}

const profileHeader = (page: Page) => page.getByRole("region", { name: "Profile" });

test("a profile is a real page for crawlers; upper case redirects; an unknown name is a 404", async ({
  page,
  request,
}) => {
  const url = `/u/${star.username}`;
  const response = await request.get(url);
  expect(response.status()).toBe(200);
  const html = await response.text();
  expect(html).toContain(`<title>@${star.username} · Rumor Zero</title>`);
  expect(html).toMatch(new RegExp(`property="og:title" content="@${star.username} · Rumor Zero"`));
  expect(html).toContain('property="og:type" content="profile"');
  expect(html).toMatch(
    /property="og:image" content="http:\/\/localhost:3000\/opengraph-image\.png/,
  );
  expect(html).toMatch(/name="twitter:image" content="http:\/\/localhost:3000\/twitter-image\.png/);
  expect(html).toContain(`rel="canonical" href="http://localhost:3000${url}"`);
  expect(html).not.toContain('content="noindex');
  expect(html).toContain(`@${star.username}`);

  // The same page by a differently cased address.
  await page.goto(`/u/${star.username.toUpperCase()}`);
  await expect(page).toHaveURL(new RegExp(`${url}$`), NAVIGATION);
  await expect(page.getByRole("heading", { level: 1, name: `@${star.username}` })).toBeVisible(
    NAVIGATION,
  );

  const missing = await request.get("/u/nobody_here_9x");
  expect(missing.status()).toBe(404);
  expect(await missing.text()).toContain("noindex");
  await page.goto("/u/nobody_here_9x");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});

test("a visitor can read a profile and is sent to log in to follow", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`/u/${star.username}`);
  await expect(page.getByRole("heading", { level: 1, name: `@${star.username}` })).toBeVisible();
  const follow = page.getByRole("link", { name: "Follow", exact: true });
  await expect(follow).toHaveAttribute("href", `/login?next=%2Fu%2F${star.username}`);
  // The Following tab is for signed-in users only.
  await page.goto("/home");
  await expect(page.getByRole("tab", { name: "Following" })).toHaveCount(0);
});

test("the profile and the lists fit a phone, and the Follow button works there", async () => {
  const page = fan.page;
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of [`/u/${star.username}`, `/u/${star.username}/followers`, "/home"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeAttached(NAVIGATION);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  }
  await page.goto(`/u/${star.username}`);
  await page.getByRole("button", { name: "Follow", exact: true }).click();
  await expect(page.getByRole("button", { name: "Following" })).toBeVisible();
  await page.getByRole("button", { name: "Following" }).click();
  await expect(page.getByRole("button", { name: "Follow", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 900 });
});

test("A follows B, B posts, A sees it under Following; unfollowing takes it away", async () => {
  const text = `I think ${marker("follow")}`;

  // A finds B (a profile is public) and follows.
  await fan.page.goto(`/u/${star.username}`);
  await expect(
    fan.page.getByRole("heading", { level: 1, name: `@${star.username}` }),
  ).toBeVisible();
  await expect(profileHeader(fan.page).getByRole("link", { name: /Followers/ })).toContainText("0");
  await fan.page.getByRole("button", { name: "Follow", exact: true }).click();
  await expect(fan.page.getByRole("button", { name: "Following" })).toBeVisible();
  await expect(profileHeader(fan.page).getByRole("link", { name: /Followers/ })).toContainText("1");

  // B posts afterwards. A's Following tab (first opened now) shows it.
  await postOpinion(star.page, text);
  await fan.page.goto("/home");
  await fan.page.getByRole("tab", { name: "Following" }).click();
  const card = fan.page.getByRole("article").filter({ hasText: text });
  await expect(card).toBeVisible();
  // The author link on the card goes back to B's profile.
  await card.getByRole("link", { name: new RegExp(`@${star.username}`) }).click();
  await expect(fan.page).toHaveURL(new RegExp(`/u/${star.username}$`), NAVIGATION);

  // The lists show the follow from both sides.
  await profileHeader(fan.page)
    .getByRole("link", { name: /Followers/ })
    .click();
  await expect(fan.page).toHaveURL(new RegExp(`/u/${star.username}/followers$`), NAVIGATION);
  await expect(fan.page.getByRole("article").filter({ hasText: `@${fan.username}` })).toBeVisible(
    NAVIGATION,
  );
  await fan.page.goto(`/u/${fan.username}/following`);
  const row = fan.page.getByRole("article").filter({ hasText: `@${star.username}` });
  await expect(row.getByRole("button", { name: "Following" })).toBeVisible(NAVIGATION);

  // Unfollow from the profile; the Following tab is empty again (the cache is cleared at once).
  await fan.page.goto(`/u/${star.username}`);
  await fan.page.getByRole("button", { name: "Following" }).click();
  await expect(fan.page.getByRole("button", { name: "Follow", exact: true })).toBeVisible();
  await expect(profileHeader(fan.page).getByRole("link", { name: /Followers/ })).toContainText("0");
  await fan.page.goto("/home");
  await fan.page.getByRole("tab", { name: "Following" }).click();
  await expect(fan.page.getByText("Follow people to see their posts here")).toBeVisible();
  await expect(fan.page.getByRole("article").filter({ hasText: text })).toHaveCount(0);
  await fan.page.getByRole("button", { name: "See Recent" }).click();
  await expect(fan.page.getByRole("article").filter({ hasText: text })).toBeVisible();
});

test("your own post shows in your Following tab at once, and your own profile has no Follow", async () => {
  const page = star.page;
  const text = `I think ${marker("own")}`;
  await postOpinion(page, text);
  await page.getByRole("tab", { name: "Following" }).click();
  await expect(page.getByRole("article").filter({ hasText: text })).toBeVisible();

  await page.goto(`/u/${star.username}`);
  await expect(page.getByRole("link", { name: /Edit profile/ })).toHaveAttribute(
    "href",
    "/settings",
  );
  await expect(page.getByRole("button", { name: /Follow/ })).toHaveCount(0);
  await expect(page.getByRole("article").filter({ hasText: text })).toBeVisible();
  // The filter narrows the list: these are opinions.
  await page.getByRole("button", { name: "Facts" }).click();
  await expect(page.getByText("No fact posts yet")).toBeVisible();
  await page.getByRole("button", { name: "Opinions" }).click();
  await expect(page.getByRole("article").filter({ hasText: text })).toBeVisible();
});

test("B likes and comments on A's post; counts survive a reload; B takes both back", async () => {
  const text = `I think ${marker("engage")}`;
  const remark = `Well put ${marker("remark")}`;
  await postOpinion(star.page, text);

  // B finds the post in Recent and likes it from the card; the glyph and count flip at once.
  await fan.page.goto("/home");
  const card = fan.page.getByRole("article").filter({ hasText: text });
  await expect(card).toBeVisible(NAVIGATION);
  await card.getByRole("button", { name: "Like 0" }).click();
  await expect(card.getByRole("button", { name: "Like 1" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  // A reload brings the server's numbers: the like stuck, and it is B's.
  await fan.page.reload();
  const reloaded = fan.page.getByRole("article").filter({ hasText: text });
  await expect(reloaded.getByRole("button", { name: "Like 1" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  // A sees one like on their own post, not marked as theirs.
  await star.page.goto("/home");
  const own = star.page.getByRole("article").filter({ hasText: text });
  await expect(own.getByRole("button", { name: "Like 1" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );

  // B opens the post and comments (Ctrl+Enter), then the heading and counts follow.
  await reloaded.getByRole("link", { name: "Comments 0" }).click();
  await expect(fan.page).toHaveURL(/\/p\/[0-9a-f-]{36}#comments$/, NAVIGATION);
  await expect(fan.page.getByRole("heading", { name: "Comments (0)" })).toBeVisible(NAVIGATION);
  await expect(fan.page.getByText("No comments yet")).toBeVisible();
  const box = fan.page.getByRole("textbox", { name: "Add a comment" });
  await box.fill(remark);
  await box.press("Control+Enter");
  await expect(fan.page.getByRole("heading", { name: "Comments (1)" })).toBeVisible();
  const mine = fan.page.getByRole("article").filter({ hasText: remark });
  await expect(mine).toBeVisible();
  await expect(box).toHaveValue("");

  // A opens the same post: B's comment is there, with no Delete button for A.
  await star.page.goto(fan.page.url().replace(/#.*/, ""));
  const theirs = star.page.getByRole("article").filter({ hasText: remark });
  await expect(theirs).toBeVisible(NAVIGATION);
  await expect(theirs.getByRole("button", { name: "Delete" })).toHaveCount(0);

  // B deletes the comment after a confirmation; it is gone for A too after a reload.
  await mine.getByRole("button", { name: "Delete" }).click();
  await fan.page
    .getByRole("dialog", { name: "Delete this comment?" })
    .getByRole("button", { name: "Delete comment" })
    .click();
  await expect(fan.page.getByRole("heading", { name: "Comments (0)" })).toBeVisible();
  await expect(fan.page.getByText(remark)).toHaveCount(0);
  await star.page.reload();
  await expect(star.page.getByRole("heading", { name: "Comments (0)" })).toBeVisible(NAVIGATION);
  await expect(star.page.getByText(remark)).toHaveCount(0);

  // B takes the like back from the post page.
  await fan.page.getByRole("button", { name: "Like 1" }).click();
  await expect(fan.page.getByRole("button", { name: "Like 0" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("a visitor sees the counts and is sent to log in to like or comment", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const text = `I think ${marker("visitor-like")}`;
  await postOpinion(star.page, text);
  await page.goto("/home");
  const card = page.getByRole("article").filter({ hasText: text });
  await expect(card).toBeVisible(NAVIGATION);
  await expect(card.getByRole("link", { name: "Like 0" })).toHaveAttribute(
    "href",
    /^\/login\?next=%2Fp%2F[0-9a-f-]{36}$/,
  );
  await card.getByRole("link", { name: "Comments 0" }).click();
  await expect(page.getByRole("heading", { name: "Comments (0)" })).toBeVisible(NAVIGATION);
  await expect(page.getByRole("link", { name: "Log in to comment" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Add a comment" })).toHaveCount(0);
});

test("the post page and its discussion fit a phone", async () => {
  const page = fan.page;
  await page.setViewportSize({ width: 390, height: 844 });
  const text = `I think ${marker("phone-like")}`;
  await postOpinion(star.page, text);
  await page.goto("/home");
  await page
    .getByRole("article")
    .filter({ hasText: text })
    .getByRole("link", { name: "Comments 0" })
    .click();
  await expect(page.getByRole("heading", { name: "Comments (0)" })).toBeVisible(NAVIGATION);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await page.setViewportSize({ width: 1280, height: 900 });
});

// ---------- reposts and bookmarks (Part 7B) ----------

const followingTab = (page: Page) => page.getByRole("tab", { name: "Following" });

test("B reposts a third person's post; A, who follows B, sees it with the live label, then 'no longer available'", async () => {
  const text = `Rain is wet ${marker("repost")}`;
  const postId = seedPost(text, { fact: true });

  // B finds the post in Recent and reposts it from the card; the button flips at once.
  await star.page.goto("/home");
  const original = star.page.getByRole("article").filter({ hasText: text });
  await expect(original).toBeVisible(NAVIGATION);
  await original.getByRole("button", { name: "Repost 0" }).click();
  await expect(original.getByRole("button", { name: "Repost 1" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  // The post's own page agrees after a reload: one repost, and it is B's.
  await star.page.goto(`/p/${postId}`);
  await expect(star.page.getByRole("button", { name: "Repost 1" })).toHaveAttribute(
    "aria-pressed",
    "true",
    NAVIGATION,
  );

  // A follows B (which also clears A's cached Following page) and sees "Reposted by B".
  await fan.page.goto(`/u/${star.username}`);
  await fan.page.getByRole("button", { name: "Follow", exact: true }).click();
  await expect(fan.page.getByRole("button", { name: "Following" })).toBeVisible();
  await fan.page.goto("/home");
  await followingTab(fan.page).click();
  const reposted = fan.page.getByRole("article").filter({ hasText: text });
  await expect(reposted).toBeVisible(NAVIGATION);
  await expect(reposted).toContainText("Reposted by");
  await expect(reposted.getByRole("link", { name: `@${star.username}` })).toBeVisible();
  await expect(reposted).toContainText("CHECKING FACTS…");
  // A repost shows the original's live label: the moderator's verdict reaches it with no new check.
  setPostState(postId, "verified_true");
  await fan.page.reload();
  await followingTab(fan.page).click();
  await expect(
    fan.page.getByRole("article").filter({ hasText: text }).getByText("VERIFIED 94%"),
  ).toBeVisible(NAVIGATION);

  // The original is removed: the repost stays, the text goes.
  setPostState(postId, "removed");
  await fan.page.reload();
  await followingTab(fan.page).click();
  const gone = fan.page
    .getByRole("article")
    .filter({ hasText: "This post is no longer available" });
  await expect(gone.first()).toBeVisible(NAVIGATION);
  await expect(gone.first()).toContainText("Reposted by");
  await expect(fan.page.getByText(text)).toHaveCount(0);
  // A cannot undo B's repost.
  await expect(gone.first().getByRole("button", { name: "Undo repost" })).toHaveCount(0);

  // B undoes it from their own profile, though the original is gone.
  await star.page.goto(`/u/${star.username}`);
  const mine = star.page
    .getByRole("article")
    .filter({ hasText: "This post is no longer available" });
  await expect(mine).toHaveCount(1, NAVIGATION);
  await mine.getByRole("button", { name: "Undo repost" }).click();
  await expect(star.page.getByText("Repost removed.", { exact: true })).toBeVisible();
  await expect(mine).toHaveCount(0);

  // A unfollows B again (the follow is left as found), and B's repost is gone from A's feed.
  await fan.page.goto(`/u/${star.username}`);
  await fan.page.getByRole("button", { name: "Following" }).click();
  await expect(fan.page.getByRole("button", { name: "Follow", exact: true })).toBeVisible();
});

test("a bookmark is private: it appears on /bookmarks for its owner and for nobody else", async () => {
  const text = `I think ${marker("bookmark")}`;
  await postOpinion(star.page, text);

  await fan.page.goto("/home");
  const card = fan.page.getByRole("article").filter({ hasText: text });
  await expect(card).toBeVisible(NAVIGATION);
  await card.getByRole("button", { name: "Bookmark" }).click();
  await expect(card.getByRole("button", { name: "Bookmark" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  // On /bookmarks (from the rail) the post is there, with its bookmark on, and survives a reload.
  await fan.page.getByRole("complementary").getByRole("link", { name: "Bookmarks" }).click();
  await expect(fan.page).toHaveURL(/\/bookmarks$/, NAVIGATION);
  await expect(fan.page.getByRole("heading", { level: 1, name: "Bookmarks" })).toBeVisible();
  const saved = fan.page.getByRole("article").filter({ hasText: text });
  await expect(saved).toBeVisible(NAVIGATION);
  await fan.page.reload();
  await expect(
    fan.page
      .getByRole("article")
      .filter({ hasText: text })
      .getByRole("button", { name: "Bookmark" }),
  ).toHaveAttribute("aria-pressed", "true", NAVIGATION);

  // The author's own list is empty: nobody sees anyone else's bookmarks, and nothing counts them.
  await star.page.goto("/bookmarks");
  await expect(star.page.getByText("No bookmarks yet")).toBeVisible(NAVIGATION);
  await expect(
    star.page.getByText("Posts you bookmark appear here. Only you can see them."),
  ).toBeVisible();
  await star.page.goto("/home");
  const theirs = star.page.getByRole("article").filter({ hasText: text });
  await expect(theirs.getByRole("button", { name: "Bookmark" })).toHaveAttribute(
    "aria-pressed",
    "false",
    NAVIGATION,
  );

  // B takes it off the list; after a reload it is gone and the empty state is back.
  await saved.getByRole("button", { name: "Bookmark" }).click();
  await expect(saved.getByRole("button", { name: "Bookmark" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await fan.page.reload();
  await expect(fan.page.getByText("No bookmarks yet")).toBeVisible(NAVIGATION);
});

test("Repost is disabled, with the reason, on your own post and on a FALSE one; visitors are sent to log in", async ({
  page,
}) => {
  const own = `I think ${marker("own")}`;
  await postOpinion(star.page, own);
  const falseText = `Cats fly ${marker("false")}`;
  const falseId = seedPost(falseText, { fact: true });
  setPostState(falseId, "verified_false");

  await star.page.goto("/home");
  const mine = star.page.getByRole("article").filter({ hasText: own });
  await expect(mine).toBeVisible(NAVIGATION);
  const ownButton = mine.getByRole("button", { name: "Repost 0" });
  await expect(ownButton).toHaveAttribute("aria-disabled", "true");
  await expect(ownButton).toHaveAttribute("title", "You can't repost your own post.");
  await ownButton.click({ force: true });
  await expect(star.page.getByText("You can't repost your own post.").first()).toBeVisible();
  // Nothing was sent: the count is still 0 after a reload.
  await star.page.reload();
  await expect(
    star.page
      .getByRole("article")
      .filter({ hasText: own })
      .getByRole("button", { name: "Repost 0" }),
  ).toBeVisible(NAVIGATION);

  await fan.page.goto("/home");
  const falseCard = fan.page.getByRole("article").filter({ hasText: falseText });
  await expect(falseCard).toBeVisible(NAVIGATION);
  await expect(falseCard.getByRole("button", { name: "Repost 0" })).toHaveAttribute(
    "title",
    "Posts labelled FALSE can't be reposted.",
  );
  // It can still be bookmarked (private, any state).
  await expect(falseCard.getByRole("button", { name: "Bookmark" })).not.toHaveAttribute(
    "aria-disabled",
    "true",
  );

  // A visitor reads the counts and is sent to log in.
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/home");
  const visitorCard = page.getByRole("article").filter({ hasText: own });
  await expect(visitorCard).toBeVisible(NAVIGATION);
  const next = /^\/login\?next=%2Fp%2F[0-9a-f-]{36}$/;
  await expect(visitorCard.getByRole("link", { name: "Repost 0" })).toHaveAttribute("href", next);
  await expect(visitorCard.getByRole("link", { name: "Bookmark" })).toHaveAttribute("href", next);
  await page.goto("/bookmarks");
  await expect(page).toHaveURL(/\/login\?next=%2Fbookmarks$/, NAVIGATION);
});

test("a card with four actions and the bookmarks page fit a phone", async () => {
  const page = fan.page;
  await page.setViewportSize({ width: 390, height: 844 });
  const text = `I think ${marker("phone-actions")}`;
  await postOpinion(star.page, text);
  await page.goto("/home");
  const card = page.getByRole("article").filter({ hasText: text });
  await expect(card.getByRole("button", { name: "Repost 0" })).toBeVisible(NAVIGATION);
  await expect(card.getByRole("button", { name: "Bookmark" })).toBeVisible();
  for (const path of ["/home", "/bookmarks"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeAttached(NAVIGATION);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
  await page.setViewportSize({ width: 1280, height: 900 });
});
