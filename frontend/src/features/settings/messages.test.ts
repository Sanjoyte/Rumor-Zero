import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import { SETTINGS_MESSAGES, settingsErrorMessage } from "./messages";

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
