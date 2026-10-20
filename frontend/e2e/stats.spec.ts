import { expect, test } from "@playwright/test";
import { confidenceThreshold, logIn, seedAuthor, seedCheckedFacts } from "./helpers";

/**
 * Part 11D against the real stack. Authors are seeded (no sign-up: the suite is bounded by
 * allauth's 20 a minute) and their facts are checked by the real pipeline stub, so the verdict,
 * the ledger and the stats come from the real services. The threshold is read from the backend's
 * own PlatformSettings, which are the developer's seed (85 by default).
 */
test("a #true fact's page shows the meter at 95% with the threshold, the tiles and the spread chart", async ({
  page,
}) => {
  const author = seedAuthor("stat");
  const [postId] = seedCheckedFacts(author.username, 1);
  const threshold = confidenceThreshold();

  await page.goto(`/p/${postId}`);
  await expect(page.getByRole("heading", { name: "How this was checked" })).toBeVisible();
  await expect(
    page.getByRole("img", {
      name: `Confidence 95%. The automatic label threshold is ${threshold}%.`,
    }),
  ).toBeVisible();
  await expect(page.getByText(`Auto-label threshold ${threshold}%`)).toBeVisible();

  // The tiles are paragraphs; the hidden table repeats the numbers, so match the visible ones.
  const tiles = page.locator("p");
  await expect(tiles.getByText("Confidence", { exact: true })).toBeVisible();
  await expect(tiles.getByText("95%", { exact: true })).toBeVisible();
  await expect(page.getByText("Threshold and margin")).toBeVisible();
  await expect(
    page.getByText(
      95 >= threshold ? `+${95 - threshold} points` : `Below today's threshold of ${threshold}%`,
    ),
  ).toBeVisible();
  await expect(page.getByText("Time to verdict")).toBeVisible();

  // The spread chart: present, with a text alternative, and nothing yet.
  await expect(page.getByRole("heading", { name: "Reposts and likes" })).toBeVisible();
  await expect(page.getByRole("img", { name: /^Reposts and likes per day/ })).toBeVisible();
  await expect(page.getByText("No reposts or likes yet.")).toBeVisible();
  const table = page.getByRole("table", { name: "First 14 days after posting (UTC)" });
  await expect(table.getByRole("row")).toHaveCount(15);
});

test("a profile shows the credibility ring, the counts and the trend, and its owner sees the history", async ({
  page,
}) => {
  const author = seedAuthor("trend");
  seedCheckedFacts(author.username, 3);

  // A visitor: the ring says 62 (100 · (5 + 3) / (10 + 3), half up), no private history.
  await page.goto(`/u/${author.username}`);
  const widget = page.getByRole("region", { name: "Credibility" });
  await expect(widget.getByRole("img", { name: "Credibility score 62 out of 100." })).toBeVisible();
  await expect(widget.getByText("3 verified")).toBeVisible();
  await expect(widget.getByText("0 FALSE")).toBeVisible();
  await expect(widget.getByText("Last 30 days", { exact: true })).toBeVisible();
  await expect(
    widget.getByRole("img", { name: /^Credibility rose from 50 to 62 over the last 30 days\.$/ }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your credibility history" })).toHaveCount(0);

  // The owner: the same widget, plus the panel with the real score and the three rows.
  await logIn(page, author);
  await page.goto(`/u/${author.username}`);
  await expect(page.getByRole("heading", { name: "Your credibility history" })).toBeVisible();
  await expect(page.getByText("Your score: 62")).toBeVisible();
  await expect(page.getByText(/^Others see New/)).toHaveCount(0);
  await page.getByRole("button", { name: /Show history \(3\)/ }).click();
  const rows = page
    .getByRole("list")
    .filter({ hasText: "Fact verified true" })
    .getByRole("listitem");
  await expect(rows).toHaveCount(3);
  await expect(page.getByRole("link", { name: "Ask for another look" })).toHaveCount(0);
});
