import { describe, expect, it } from "vitest";
import {
  countCharacters,
  formatCompactNumber,
  formatConfidence,
  formatCount,
  formatFullDateTime,
  formatMonthYear,
  formatRelativeTime,
} from "./format";

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

describe("countCharacters", () => {
  it("counts code points, like Python's len and Postgres's char_length", () => {
    expect(countCharacters("")).toBe(0);
    expect(countCharacters("abc")).toBe(3);
    expect(countCharacters("\u{1F600}")).toBe(1); // 2 UTF-16 units
    expect(countCharacters("\u{1F600}".repeat(500))).toBe(500);
    expect(countCharacters("caf\u00e9")).toBe(4);
    expect(countCharacters("a\nb")).toBe(3);
  });

  it("counts a combining sequence as its code points, as the server does", () => {
    expect(countCharacters("e\u0301")).toBe(2);
  });
});

describe("formatFullDateTime", () => {
  it("prints an exact UTC time, whatever the viewer's zone", () => {
    expect(formatFullDateTime("2026-10-09T14:05:00Z")).toBe("Oct 9, 2026, 2:05 PM UTC");
    expect(formatFullDateTime("2026-01-01T00:00:00Z")).toBe("Jan 1, 2026, 12:00 AM UTC");
    expect(formatFullDateTime(new Date("2026-10-09T23:59:00Z"))).toBe("Oct 9, 2026, 11:59 PM UTC");
  });

  it("gives nothing for an invalid date", () => {
    expect(formatFullDateTime("not a date")).toBe("");
  });
});

describe("formatMonthYear", () => {
  it("prints the month and year in UTC", () => {
    expect(formatMonthYear("2024-03-15T10:00:00Z")).toBe("March 2024");
    expect(formatMonthYear("2026-01-01T00:00:00Z")).toBe("January 2026");
    expect(formatMonthYear(new Date("2026-12-31T23:59:59Z"))).toBe("December 2026");
  });

  it("does not move across a month boundary with the viewer's zone", () => {
    expect(formatMonthYear("2026-10-31T23:30:00Z")).toBe("October 2026");
    expect(formatMonthYear("2026-11-01T00:30:00Z")).toBe("November 2026");
  });

  it("gives nothing for an invalid date", () => {
    expect(formatMonthYear("soon")).toBe("");
  });
});

describe("formatCount", () => {
  it("prints the whole number with a thousands separator", () => {
    expect(formatCount(0)).toBe("0");
    expect(formatCount(999)).toBe("999");
    expect(formatCount(1420)).toBe("1,420");
    expect(formatCount(1234567)).toBe("1,234,567");
  });
});
