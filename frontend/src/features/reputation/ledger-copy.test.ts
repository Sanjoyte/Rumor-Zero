import { describe, expect, it } from "vitest";
import { APPEAL_STATE_WORDS, trendSummary } from "./ledger-copy";

describe("trendSummary", () => {
  it("says where the line went", () => {
    expect(trendSummary(60, 68)).toBe("Credibility rose from 60 to 68 over the last 30 days.");
    expect(trendSummary(68, 60)).toBe("Credibility fell from 68 to 60 over the last 30 days.");
    expect(trendSummary(62, 62)).toBe("Credibility stayed at 62 over the last 30 days.");
  });
});

describe("APPEAL_STATE_WORDS", () => {
  it("has a phrase for every state, never saying debunked", () => {
    expect(Object.keys(APPEAL_STATE_WORDS).sort()).toEqual(["open", "overturned", "upheld"]);
    expect(Object.values(APPEAL_STATE_WORDS).join(" ")).not.toMatch(/debunk/i);
  });
});
