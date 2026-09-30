import { describe, expect, it } from "vitest";
import { formatCompactNumber, formatConfidence, formatRelativeTime } from "./format";

const NOW = new Date("2026-09-30T12:00:00Z");

describe("formatRelativeTime", () => {
  it.each([
    ["2026-09-30T11:59:45Z", "now"],
    ["2026-09-30T12:00:30Z", "now"], // a little clock skew into the future
    ["2026-09-30T11:55:00Z", "5m"],
    ["2026-09-30T09:00:00Z", "3h"],
    ["2026-09-28T12:00:00Z", "2d"],
    ["2026-09-23T12:00:00Z", "Sep 23"],
    ["2025-12-31T23:00:00Z", "Dec 31, 2025"],
  ])("%s gives %s", (iso, expected) => {
    expect(formatRelativeTime(iso, NOW)).toBe(expected);
  });

  it("accepts a Date and returns an empty string for garbage", () => {
    expect(formatRelativeTime(new Date("2026-09-30T11:00:00Z"), NOW)).toBe("1h");
    expect(formatRelativeTime("not a date", NOW)).toBe("");
  });
});

describe("formatCompactNumber", () => {
  it.each([
    [0, "0"],
    [999, "999"],
    [1200, "1.2K"],
    [15300, "15.3K"],
    [3_400_000, "3.4M"],
  ])("%d gives %s", (n, expected) => {
    expect(formatCompactNumber(n)).toBe(expected);
  });
});

describe("formatConfidence", () => {
  it("rounds the decimal string to a whole percent", () => {
    expect(formatConfidence("94.00")).toBe("94%");
    expect(formatConfidence("87.6")).toBe("88%");
    expect(formatConfidence(50)).toBe("50%");
  });

  it("returns an empty string when there is no score", () => {
    expect(formatConfidence(null)).toBe("");
    expect(formatConfidence(undefined)).toBe("");
    expect(formatConfidence("")).toBe("");
    expect(formatConfidence("n/a")).toBe("");
  });
});
