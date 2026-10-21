import { expect, test, type Page } from "@playwright/test";
import {
  logIn,
  makePhoto,
  marker,
  moderateAccount,
  seedAuthor,
  type SeededAuthor,
} from "./helpers";

/**
 * Part 14B: a profile photo from the settings page to every place it shows, through the real
 * relay. The person is seeded (no sign-up: the suite is bounded by allauth's 20 sign-ups a
 * minute), and `moderateAccount` plays the moderator the way Django Admin's actions do.
 */

const AVATAR_URL = /\/api\/v1\/avatars\/[0-9a-f-]{36}\/[0-9a-f]{16}-(96|256)\.webp$/;

/** The chunk names of a WebP file, read from its bytes. */
function riffChunks(data: Buffer): string[] {
  expect(data.subarray(0, 4).toString("latin1")).toBe("RIFF");
  expect(data.subarray(8, 12).toString("latin1")).toBe("WEBP");
  const names: string[] = [];
  let position = 12;
  while (position + 8 <= data.length) {
    names.push(data.subarray(position, position + 4).toString("latin1"));
    const size = data.readUInt32LE(position + 4);
    position += 8 + size + (size & 1);
  }
  return names;
}

async function postOpinion(page: Page, text: string) {
  await page.goto("/home");
  await page.getByRole("complementary").getByRole("button", { name: "New post" }).click();
  const dialog = page.getByRole("dialog", { name: "New post" });
  await dialog.getByRole("textbox", { name: "Post text" }).fill(text);
  await dialog.getByRole("radio", { name: "Opinion" }).click();
  await dialog.getByRole("button", { name: "Post opinion" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("article").filter({ hasText: text })).toHaveCount(1);
}

/** Chooses `file` on /settings, confirms it, and waits for the toast. */
async function uploadPhoto(page: Page, file: string) {
  await page.goto("/settings");
  await page.getByTestId("photo-input").setInputFiles(file);
  await page.getByRole("button", { name: "Use this photo" }).click();
  await expect(page.getByText("Photo saved.")).toBeVisible();
}

const railPhoto = (page: Page) =>
  page.getByRole("complementary").locator("img[src*='/api/v1/avatars/']");

async function loaded(page: Page, selector: string) {
  return page
    .locator(selector)
    .first()
    .evaluate((image) => {
      const img = image as HTMLImageElement;
      return img.complete && img.naturalWidth > 0;
    });
}

test("upload a photo: preview, progress, the rail, the cards, and the cached bytes", async ({
  page,
}, testInfo) => {
  const account: SeededAuthor = seedAuthor("avu");
  const claim = `Photo post ${marker("av")}`;
  const file = testInfo.outputPath("holiday.jpg");
  makePhoto(file, { width: 640, height: 400, gps: true });
  await logIn(page, account);
  await postOpinion(page, claim);

  // The card starts on initials, with the rules in plain words.
  await page.goto("/settings");
  await expect(page.getByRole("heading", { level: 3, name: "Profile photo" })).toBeVisible();
  await expect(page.getByText("remove location and camera data")).toBeVisible();
  await expect(railPhoto(page)).toHaveCount(0);

  // Choose a file: a square preview first, nothing sent yet. Hold the request so the progress
  // bar can be seen.
  let sent = 0;
  await page.route("**/api/v1/me/avatar/", async (route) => {
    sent += 1;
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  });
  await page.getByTestId("photo-input").setInputFiles(file);
  const preview = page.getByRole("img", { name: "Preview of your new photo" });
  await expect(preview).toBeVisible();
  expect(sent).toBe(0);
  const box = await preview.boundingBox();
  expect(Math.round(box!.width)).toBe(Math.round(box!.height));

  // Use it: the progress bar shows while the request is held, then the toast.
  await page.getByRole("button", { name: "Use this photo" }).click();
  await expect(page.getByRole("progressbar", { name: "Photo upload progress" })).toBeVisible();
  await expect(page.getByText("Photo saved.")).toBeVisible();
  expect(sent).toBe(1);
  await expect(preview).toBeHidden();
  await page.unroute("**/api/v1/me/avatar/");

  // The rail (and everything else that reads /me) now shows the 256 px photo, and it loads.
  await expect(railPhoto(page).first()).toHaveAttribute("src", /-256\.webp$/);
  const railSrc = (await railPhoto(page).first().getAttribute("src"))!;
  expect(railSrc).toMatch(AVATAR_URL);
  await expect.poll(() => loaded(page, "aside img[src*='/api/v1/avatars/']")).toBe(true);
  await expect(page.getByRole("button", { name: "Change photo" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove photo" })).toBeVisible();

  // The profile: the header uses the 256 px image, the person's own post card the 96 px one.
  await page.goto(`/u/${account.username}`);
  const card = page.getByRole("article").filter({ hasText: claim });
  await expect(card.locator("img[src*='/api/v1/avatars/']").first()).toHaveAttribute(
    "src",
    /-96\.webp$/,
  );
  await expect(page.locator("main img[src$='-256.webp']").first()).toBeVisible();
  const cardSrc = (await card.locator("img[src*='/api/v1/avatars/']").first().getAttribute("src"))!;
  const small = await page.request.get(cardSrc);
  expect(small.status()).toBe(200);

  // The bytes, through the relay on the frontend's own origin.
  const image = await page.request.get(railSrc);
  expect(image.status()).toBe(200);
  const headers = image.headers();
  expect(headers["content-type"]).toBe("image/webp");
  expect(headers["cache-control"]).toBe("public, max-age=31536000, immutable");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["content-security-policy"]).toBe("default-src 'none'; sandbox");
  expect(headers["content-disposition"]).toBe('inline; filename="avatar.webp"');
  expect(headers.etag).toMatch(/^"[0-9a-f]{16}-256"$/);
  // Nothing of the original but pixels: a bare picture chunk, no EXIF, ICC or XMP.
  expect(riffChunks(await image.body())).toEqual(["VP8 "]);
  expect((await image.body()).includes(Buffer.from("E2ECameraMaker"))).toBe(false);

  // A repeat request with the ETag is a 304 with no body, through the relay.
  const again = await page.request.get(railSrc, { headers: { "If-None-Match": headers.etag } });
  expect(again.status()).toBe(304);
  expect((await again.body()).length).toBe(0);
  expect(again.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
});

test("a moderator removes the photo: initials at once; blocking turns the uploader off", async ({
  page,
}, testInfo) => {
  const account = seedAuthor("avm");
  const file = testInfo.outputPath("portrait.jpg");
  makePhoto(file, { width: 400, height: 640, gps: false });
  await logIn(page, account);
  await uploadPhoto(page, file);
  const oldSrc = (await railPhoto(page).first().getAttribute("src"))!;
  expect((await page.request.get(oldSrc)).status()).toBe(200);

  // Remove photo (Django Admin's action): the next load shows initials, the old URL is gone.
  moderateAccount(account.username, "remove_photo");
  await page.reload();
  await expect(railPhoto(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Upload photo" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Remove photo" })).toHaveCount(0);
  const gone = await page.request.get(oldSrc);
  expect(gone.status()).toBe(404);
  expect(await gone.json()).toMatchObject({ code: "not_found" });

  // The person puts a new one up, then takes it down themselves, without a confirmation dialog.
  await uploadPhoto(page, file);
  await expect(railPhoto(page).first()).toBeVisible();
  await page.getByRole("button", { name: "Remove photo" }).click();
  await expect(page.getByText("Photo removed.")).toBeVisible();
  await expect(railPhoto(page)).toHaveCount(0);
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // Block photo uploads: the card says why and offers no upload; Allow brings the button back.
  moderateAccount(account.username, "block_photo_uploads");
  await page.reload();
  await expect(
    page.getByText("A moderator turned off photo uploads for your account."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Upload photo|Change photo/ })).toHaveCount(0);
  moderateAccount(account.username, "allow_photo_uploads");
  await page.reload();
  await expect(page.getByRole("button", { name: "Upload photo" })).toBeEnabled();
  await expect(page.getByText("turned off photo uploads")).toHaveCount(0);
});

test("a file the browser can't use is refused before anything is sent", async ({
  page,
}, testInfo) => {
  const account = seedAuthor("avb");
  await logIn(page, account);
  await page.goto("/settings");
  let requests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/me/avatar/")) requests += 1;
  });

  const tiny = testInfo.outputPath("tiny.jpg");
  makePhoto(tiny, { width: 100, height: 100, gps: false });
  await page.getByTestId("photo-input").setInputFiles(tiny);
  await expect(page.getByRole("alert").filter({ hasText: "too small" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Preview of your new photo" })).toHaveCount(0);

  await page.getByTestId("photo-input").setInputFiles({
    name: "notes.png",
    mimeType: "image/png",
    buffer: Buffer.from("this is not a picture"),
  });
  await expect(page.getByRole("alert").filter({ hasText: "can't read that file" })).toBeVisible();
  expect(requests).toBe(0);
});
