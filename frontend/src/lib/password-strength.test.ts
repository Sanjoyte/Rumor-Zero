import { describe, expect, it } from "vitest";
import { PASSWORD_STRENGTH_LABELS, scorePassword } from "./password-strength";

describe("scorePassword", () => {
  it.each([
    ["", 0],
    ["abc", 1],
    ["Ab1!", 1], // many classes but shorter than 8
    ["abcdefgh", 1], // long enough but one class
    ["abcdefg1", 2], // 8 chars, 2 classes
    ["abcdefg1X", 3], // 8+ chars, 3 classes
    ["abcdefghijkl1", 3], // 12+ chars, 2 classes
    ["abcdefghij1X", 4], // 12+ chars, 3 classes
    ["abcdefghijklmnop1", 4], // 16+ chars
  ])("%j gives %d", (password, expected) => {
    expect(scorePassword(password)).toBe(expected);
  });

  it("never rates a password under 8 characters above Weak", () => {
    expect(scorePassword("Aa1!Bb2@")).toBeGreaterThan(1);
    expect(scorePassword("Aa1!Bb2")).toBe(1);
  });

  it("has a label for every level", () => {
    expect(PASSWORD_STRENGTH_LABELS).toEqual(["", "Weak", "Fair", "Good", "Strong"]);
  });
});
