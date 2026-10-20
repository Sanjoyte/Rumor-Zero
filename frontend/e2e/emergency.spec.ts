import { expect, test, type Page } from "@playwright/test";
import { emergencySettings, logIn, marker, moderate, processPost, seedAuthor } from "./helpers";

/**
 * Part 11C: an eligible author posts an emergency, it is pinned on Recent, the pipeline's FALSE
 * sends it to review (still pinned), and a moderator's Mark FALSE unpins it and labels it FALSE.
 * Against the real stack, with no sign-up: authors are seeded (the suite is at 16 of allauth's 20 a
 * minute), the pipeline runs for this one post, and the moderator acts through the backend's own
 * services. The E2E backend uses the developer's own PlatformSettings, so the limits are read, not
 * assumed.
 */

const newPost = (page: Page) =>
  page.getByRole("complementary").getByRole("button", { name: "New post" });

/** Recent's pinned section ("Emergency posts"). */
const pinned = (page: Page) =>
  page
    .getByRole("tabpanel", { name: "Recent" })
    .getByRole("region", { name: /^Emergency posts$/i });

test("a new account sees why it can't post an emergency yet", async ({ page }) => {
  const limits = emergencySettings();
  test.skip(
    limits.minAccountAgeDays === 0,
    "the developer's emergency_min_account_age_days is 0: every account is old enough",
  );
  test.skip(limits.factPostsPerDay === 0, "fact posts are paused in the developer's settings");
  await logIn(page, seedAuthor("emnew"));
  await newPost(page).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await dialog.getByRole("radio", { name: "Fact" }).click();
  const toggle = dialog.getByRole("switch", { name: "Emergency post" });
  await expect(toggle).toBeDisabled();
  await expect(dialog.getByText(/^Your account is too new for emergency posts\./)).toBeVisible();
  await expect(toggle).toHaveAccessibleDescription(/Your account is too new/);
});

test("an emergency is pinned on Recent, stays pinned under review, and Mark FALSE unpins it", async ({
  page,
}) => {
  const limits = emergencySettings();
  test.skip(
    limits.perDay === 0 || limits.factPostsPerDay === 0 || limits.minReputation > 50,
    "the developer's settings make an emergency impossible (paused, or a minimum score above 50)",
  );
  const author = seedAuthor("emok", { ageDays: limits.minAccountAgeDays + 1 });
  await logIn(page, author);

  // #false: the stub answers FALSE 92, which an active emergency never takes automatically. The
  // claim avoids the word "emergency", which the chip's text match would also find.
  const claim = `Bridge ${marker("em")} #false`;
  await newPost(page).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await dialog.getByRole("textbox", { name: "Post text" }).fill(claim);
  await dialog.getByRole("radio", { name: "Fact" }).click();
  const toggle = dialog.getByRole("switch", { name: "Emergency post" });
  await expect(toggle).toBeEnabled();
  // The switch is a visually hidden input inside its track: click the track (its label).
  await toggle.check({ force: true });
  await expect(
    dialog.getByText("Use this only for urgent safety or public-health news."),
  ).toBeVisible();
  const send = dialog.getByRole("button", { name: "Post emergency, will be checked" });
  await send.click();
  await expect(dialog.getByText("Tick the box to confirm.")).toBeVisible();
  await dialog
    .getByRole("checkbox", { name: /I understand emergency posts are checked first/ })
    .check();
  await send.click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText("Posted. It's pinned while it's checked.")).toBeVisible();

  const card = pinned(page).getByRole("article").filter({ hasText: claim });
  await expect(card).toHaveCount(1);
  const href = await card.getByRole("link", { name: new RegExp(claim) }).getAttribute("href");
  const postId = href!.split("/p/")[1];
  expect(postId).toMatch(/^[0-9a-f-]{36}$/);

  let unpinned = false;
  try {
    await expect(card.getByText("EMERGENCY")).toBeVisible();

    // The pipeline's FALSE on an active emergency goes to a moderator.
    expect(processPost(postId)).toMatchObject({ status: "under_review" });
    await page.reload();
    const reviewed = pinned(page).getByRole("article").filter({ hasText: claim });
    await expect(reviewed).toHaveCount(1);
    await expect(reviewed.getByText("UNDER REVIEW")).toBeVisible();
    await expect(reviewed.getByText("EMERGENCY")).toBeVisible();

    // A moderator's Mark FALSE ends the priority at once.
    moderate(postId, "mark_false");
    unpinned = true;
    await page.reload();
    const recent = page.getByRole("tabpanel", { name: "Recent" });
    const listed = recent.getByRole("article").filter({ hasText: claim });
    await expect(listed).toHaveCount(1);
    await expect(listed.getByText("FALSE · REVIEWED")).toBeVisible();
    await expect(listed.getByText("EMERGENCY")).toHaveCount(0);
    await expect(pinned(page).getByRole("article").filter({ hasText: claim })).toHaveCount(0);
  } finally {
    if (!unpinned) {
      // Don't leave the developer's Recent feed with a pinned test post. A refusal (already
      // demoted, or FALSE) is ignored so the real failure stays the one reported.
      try {
        moderate(postId, "demote_emergency");
      } catch {
        // already not an active emergency
      }
    }
  }
});
