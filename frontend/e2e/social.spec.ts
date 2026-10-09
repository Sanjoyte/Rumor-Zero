import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { marker, signUpVerified } from "./helpers";

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
