import { expect, test, type Page } from "@playwright/test";
import { logIn, marker, seedAuthor, seedPost, setPostState } from "./helpers";

/**
 * Search (Part 12). No sign-ups (the suite already uses most of the 20 a minute), and few searches:
 * every request comes from 127.0.0.1, React's Strict Mode doubles the first fetch in dev, the
 * suite runs in parallel, and `search` is 60 a minute per address. People and posts are made
 * straight in the database; text must be plain letters, digits and spaces.
 */

// `next dev` compiles /search the first time it is visited.
const NAVIGATION = { timeout: 20_000 };

const results = (page: Page) => page.getByRole("main").getByRole("article");
const queryBox = (page: Page) =>
  page.getByRole("main").getByRole("textbox", { name: "Search query" });

test("the empty page asks for a query and fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/search");
  await expect(page.getByText("Search Rumor Zero")).toBeVisible(NAVIGATION);
  await expect(queryBox(page)).toHaveValue("");
  await expect(page.getByRole("tab", { name: "Posts" })).toHaveAttribute("aria-selected", "true");
  for (const name of ["All", "Facts", "Opinions", "Verified", "FALSE", "Under review"]) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  }
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scrollWidth).toBe(390);
});

test("a search finds a post by a stem, marks the words, and the box submits", async ({ page }) => {
  const m = marker("run");
  const id = seedPost(`She runs every morning ${m}`);
  await page.goto("/search");
  await queryBox(page).fill(`running ${m}`);
  await queryBox(page).press("Enter");
  await expect(page).toHaveURL(new RegExp(`/search\\?q=running\\+${m}$`), NAVIGATION);
  const card = results(page).filter({ hasText: m });
  await expect(card).toHaveCount(1, NAVIGATION);
  // "running" stems like "runs": the word is marked, and so is the marker.
  await expect(card.locator("mark", { hasText: /^runs$/ })).toHaveCount(1);
  await expect(card.locator("mark", { hasText: m })).toHaveCount(1);
  await expect(card.getByRole("link", { name: /She runs every morning/ })).toHaveAttribute(
    "href",
    `/p/${id}`,
  );
  // The clear button empties the field.
  await page.getByRole("button", { name: "Clear search" }).click();
  await expect(queryBox(page)).toHaveValue("");
});

test("removed and deleted posts are never found", async ({ page }) => {
  const m = marker("gone");
  seedPost(`Flood shown ${m}`);
  setPostState(seedPost(`Flood removed ${m}`), "removed");
  setPostState(seedPost(`Flood deleted ${m}`), "deleted");
  await page.goto(`/search?q=flood+${m}`);
  await expect(results(page)).toHaveCount(1, NAVIGATION);
  await expect(results(page).first()).toContainText("Flood shown");
});

test("the chips narrow the results and each is in the address", async ({ page }) => {
  const m = marker("chip");
  seedPost(`Opinion about the bridge ${m}`);
  setPostState(seedPost(`Fact about the bridge ${m}`, { fact: true }), "verified_true");
  await page.goto(`/search?q=bridge+${m}`);
  await expect(results(page)).toHaveCount(2, NAVIGATION);

  await page.getByRole("button", { name: "Verified", exact: true }).click();
  await expect(page).toHaveURL(/filter=verified/);
  await expect(results(page)).toHaveCount(1, NAVIGATION);
  await expect(results(page).first()).toContainText("Fact about the bridge");

  await page.getByRole("button", { name: "Opinions", exact: true }).click();
  await expect(page).toHaveURL(/filter=opinions/);
  await expect(results(page)).toHaveCount(1, NAVIGATION);
  await expect(results(page).first()).toContainText("Opinion about the bridge");

  // Pressing the chosen chip again is All.
  await page.getByRole("button", { name: "Opinions", exact: true }).click();
  await expect(page).not.toHaveURL(/filter=/);
  await expect(results(page)).toHaveCount(2, NAVIGATION);
});

test("People finds an account by the start of its username, `_` included", async ({ page }) => {
  const author = seedAuthor("srch");
  await page.goto(`/search?q=${author.username}&type=users`);
  await expect(page.getByRole("tab", { name: "People" })).toHaveAttribute("aria-selected", "true");
  const row = results(page).filter({ hasText: `@${author.username}` });
  await expect(row).toHaveCount(1, NAVIGATION);
  await expect(row.getByRole("link", { name: new RegExp(author.username) })).toHaveAttribute(
    "href",
    `/u/${author.username}`,
  );
  await expect(row.getByText(/Credibility/)).toBeVisible();
  // `_` is literal: a query that only matches if it were a wildcard finds nobody.
  const wildcard = author.username.replace("_", "%");
  await page.goto(`/search?q=${encodeURIComponent(wildcard)}&type=users`);
  await expect(page.getByText(/No people found for/)).toBeVisible(NAVIGATION);
});

test("a signed-in person sees their own row without a Follow button", async ({ page }) => {
  test.setTimeout(60_000);
  const author = seedAuthor("srchme");
  await logIn(page, author);
  await page.goto(`/search?q=${author.username}&type=users`);
  const row = results(page).filter({ hasText: `@${author.username}` });
  await expect(row).toHaveCount(1, NAVIGATION);
  await expect(row.getByRole("button", { name: /Follow/ })).toHaveCount(0);
});
