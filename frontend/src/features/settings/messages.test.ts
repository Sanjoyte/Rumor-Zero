import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import {
  PHOTO_MESSAGES,
  SETTINGS_MESSAGES,
  photoErrorMessage,
  settingsErrorMessage,
} from "./messages";

const error = (status: number, code = `http_${status}`) =>
  new ApiError({ status, code, detail: "server text" });

describe("settingsErrorMessage", () => {
  it.each([
    [error(429, "throttled"), SETTINGS_MESSAGES.rateLimited],
    [error(503, "backend_waking"), SETTINGS_MESSAGES.waking],
    [error(0, "network_error"), SETTINGS_MESSAGES.network],
    [error(401, "not_authenticated"), SETTINGS_MESSAGES.signedOut],
    [error(403, "email_unverified"), SETTINGS_MESSAGES.unverified],
    [error(403, "staff_account"), SETTINGS_MESSAGES.staffAccount],
    [error(409, "password_not_set"), SETTINGS_MESSAGES.noPassword],
    [error(500), SETTINGS_MESSAGES.generic],
    [new Error("boom"), SETTINGS_MESSAGES.generic],
    ["nope", SETTINGS_MESSAGES.generic],
  ])("%#", (input, message) => {
    expect(settingsErrorMessage(input)).toBe(message);
  });

  it("never shows the server's own text", () => {
    expect(settingsErrorMessage(error(500))).not.toContain("server text");
  });
});

describe("photoErrorMessage", () => {
  const withWait = (seconds: number) =>
    new ApiError({ status: 429, code: "throttled", detail: "server text", retryAfter: seconds });

  it.each([
    [error(403, "photo_uploads_blocked"), PHOTO_MESSAGES.blocked],
    [error(403, "email_unverified"), PHOTO_MESSAGES.unverified],
    [error(400, "photo_too_large"), PHOTO_MESSAGES.serverTooLarge],
    [error(413, "payload_too_large"), PHOTO_MESSAGES.serverTooLarge],
    [error(413), PHOTO_MESSAGES.serverTooLarge],
    [error(400, "photo_unsupported"), PHOTO_MESSAGES.serverUnsupported],
    [error(400, "photo_missing"), PHOTO_MESSAGES.serverUnsupported],
    [error(400, "photo_too_small"), PHOTO_MESSAGES.tooSmall],
    [error(400, "photo_too_many_pixels"), PHOTO_MESSAGES.tooManyPixels],
    [error(503, "photo_busy"), PHOTO_MESSAGES.busy],
    [error(503, "backend_waking"), SETTINGS_MESSAGES.waking],
    [error(0, "network_error"), SETTINGS_MESSAGES.network],
    [error(401, "not_authenticated"), SETTINGS_MESSAGES.signedOut],
    [error(500), SETTINGS_MESSAGES.generic],
    [new Error("boom"), SETTINGS_MESSAGES.generic],
  ])("%#", (input, message) => {
    expect(photoErrorMessage(input)).toBe(message);
  });

  it("says when to try again after the daily limit", () => {
    expect(photoErrorMessage(withWait(7200))).toBe(
      "You've changed your photo a few times today. Try again in about 2 hours.",
    );
    expect(photoErrorMessage(withWait(30))).toContain("in a minute");
  });

  it("a code wins over the status: a 503 photo_busy is not 'waking'", () => {
    expect(photoErrorMessage(error(503, "photo_busy"))).not.toBe(SETTINGS_MESSAGES.waking);
  });

  it("never shows the server's own text", () => {
    for (const code of ["photo_unsupported", "photo_too_small", "throttled", "other"]) {
      expect(photoErrorMessage(error(400, code))).not.toContain("server text");
    }
  });

  it("the photo texts are plain, end with a full stop and mention no metadata promise but ours", () => {
    for (const [key, text] of Object.entries(PHOTO_MESSAGES)) {
      if (key === "title") continue;
      expect(text.endsWith("."), key).toBe(true);
    }
    expect(PHOTO_MESSAGES.intro).toContain("remove location and camera data");
  });
});
