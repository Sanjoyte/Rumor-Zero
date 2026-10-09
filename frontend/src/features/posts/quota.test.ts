import { describe, expect, it } from "vitest";
import { formatNextSlot, quotaLine } from "./quota";
import { makeQuota } from "./test-helpers";

const NOW = new Date("2026-10-08T12:00:00Z");
const OPTIONS = { now: NOW, timeZone: "UTC" };

describe("quotaLine", () => {
  it("is hidden until the quota is known", () => {
    expect(quotaLine(null, OPTIONS)).toBeNull();
  });

  it("says how many fact posts are left", () => {
    expect(quotaLine(makeQuota({ used: 3, remaining: 7 }), OPTIONS)).toEqual({
      count: "7/10",
      text: "fact posts left",
      suffix: null,
      tone: "normal",
    });
  });

  it("says when the next one frees up once nothing is left", () => {
    const line = quotaLine(
      makeQuota({ used: 10, remaining: 0, next_slot_at: "2026-10-08T14:05:00Z" }),
      OPTIONS,
    );
    expect(line).toEqual({
      count: "0/10",
      text: "fact posts left",
      suffix: "next at 2:05 PM",
      tone: "empty",
    });
  });

  it("says 'tomorrow' when the slot frees up on another day", () => {
    const line = quotaLine(
      makeQuota({ used: 10, remaining: 0, next_slot_at: "2026-10-09T02:10:00Z" }),
      OPTIONS,
    );
    expect(line?.suffix).toBe("next tomorrow at 2:10 AM");
  });

  it("has no suffix when there is no time to show", () => {
    expect(quotaLine(makeQuota({ remaining: 0, used: 10 }), OPTIONS)?.suffix).toBeNull();
  });

  it("says fact posts are paused when the limit is 0", () => {
    expect(quotaLine(makeQuota({ limit: 0, used: 0, remaining: 0 }), OPTIONS)).toEqual({
      count: null,
      text: "Fact posts are paused right now",
      suffix: null,
      tone: "empty",
    });
  });
});

describe("formatNextSlot", () => {
  it("shows the viewer's own time zone", () => {
    expect(formatNextSlot("2026-10-08T14:05:00Z", { now: NOW, timeZone: "Asia/Dhaka" })).toBe(
      "next at 8:05 PM",
    );
  });

  it("compares days in the viewer's zone, not UTC", () => {
    // 20:00 UTC is already tomorrow in Dhaka (UTC+6) but not "now" (12:00 UTC = 18:00 there).
    expect(formatNextSlot("2026-10-08T20:00:00Z", { now: NOW, timeZone: "Asia/Dhaka" })).toBe(
      "next tomorrow at 2:00 AM",
    );
  });

  it("returns nothing for a bad date", () => {
    expect(formatNextSlot("not a date", OPTIONS)).toBe("");
  });
});
