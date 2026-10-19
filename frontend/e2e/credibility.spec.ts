import { expect, test } from "@playwright/test";
import { seedAuthor, seedCheckedFacts } from "./helpers";

/**
 * Part 11B: the public credibility score on a profile, against the real stack. The author is seeded
 * (no sign-up: the suite is at 16 of allauth's 20 a minute) and their facts are checked by the real
 * pipeline stub, so the ledger is written by the real services. The visitor isn't logged in.
 */
test("a profile shows Credibility: New until three facts are checked, then the score", async ({
  page,
}) => {
  const author = seedAuthor("cred");
  seedCheckedFacts(author.username, 2);

  await page.goto(`/u/${author.username}`);
  const profile = page.getByRole("region", { name: "Profile" });
  await expect(profile.getByText(/^Credibility: New/)).toBeVisible();
  await expect(profile.getByRole("link", { name: "How this is calculated" })).toHaveAttribute(
    "href",
    "/how-it-works#credibility",
  );

  seedCheckedFacts(author.username, 1);
  await page.reload();
  // 100 · (5 + 3) / (10 + 3) = 61.5, rounded half up.
  await expect(profile.getByText("Credibility 62", { exact: true })).toBeVisible();

  // Never on a post card: the profile's own posts carry no score.
  const cards = page.getByRole("article");
  await expect(cards).toHaveCount(3);
  for (const card of await cards.all()) {
    await expect(card).not.toContainText("Credibility");
  }
});
