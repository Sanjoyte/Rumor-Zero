// @vitest-environment node
import { describe, expect, it } from "vitest";
import { getAccessToken, setAccessToken } from "./token-store";

describe("token store (server)", () => {
  it("ignores writes, so requests can never share a token", () => {
    expect(typeof window).toBe("undefined");
    setAccessToken("leaked?");
    expect(getAccessToken()).toBeNull();
  });
});
