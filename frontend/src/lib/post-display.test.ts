import { describe, expect, it } from "vitest";
import { type PostDisplayInput, statusBadgeSpec, stripeTone } from "./post-display";

describe("statusBadgeSpec (ARCHITECTURE section 4 badge table)", () => {
  const rows: [string, PostDisplayInput, ReturnType<typeof statusBadgeSpec>][] = [
    [
      "pending",
      { status: "pending" },
      { label: "CHECKING FACTS…", glyph: "progress_activity", tone: "neutral-dashed", spin: true },
    ],
    ["published opinion", { status: "published" }, null],
    [
      "verified_true, pipeline",
      { status: "verified_true", verdictSource: "pipeline", confidenceScore: "94.00" },
      { label: "VERIFIED 94%", glyph: "check_circle", tone: "primary" },
    ],
    [
      "verified_true, moderator",
      { status: "verified_true", verdictSource: "moderator", confidenceScore: "94.00" },
      { label: "VERIFIED · REVIEWED", glyph: "check_circle", tone: "primary" },
    ],
    [
      "verified_false, pipeline",
      { status: "verified_false", verdictSource: "pipeline", confidenceScore: "88.00" },
      { label: "FALSE 88%", glyph: "cancel", tone: "error" },
    ],
    [
      "verified_false, moderator",
      { status: "verified_false", verdictSource: "moderator" },
      { label: "FALSE · REVIEWED", glyph: "cancel", tone: "error" },
    ],
    [
      "under_review",
      { status: "under_review" },
      { label: "UNDER REVIEW", glyph: "hourglass_top", tone: "review" },
    ],
    ["removed", { status: "removed" }, { label: "REMOVED", glyph: "block", tone: "neutral" }],
  ];

  it.each(rows)("%s", (_name, input, expected) => {
    expect(statusBadgeSpec(input)).toEqual(expected);
  });

  it("shows no percentage for a pipeline verdict without a score", () => {
    const spec = statusBadgeSpec({
      status: "verified_false",
      verdictSource: "pipeline",
      confidenceScore: null,
    });
    expect(spec?.label).toBe("FALSE");
  });

  it("never says debunked", () => {
    for (const [, input] of rows) {
      expect(statusBadgeSpec(input)?.label ?? "").not.toMatch(/debunk/i);
    }
  });
});

describe("stripeTone", () => {
  const cases: [PostDisplayInput, ReturnType<typeof stripeTone>][] = [
    [{ status: "verified_true" }, "primary"],
    [{ status: "verified_false" }, "error"],
    [{ status: "under_review" }, "verdict-review"],
    [{ status: "pending" }, "outline-variant"],
    [{ status: "published" }, "outline-variant"],
    [{ status: "removed" }, null],
  ];

  it.each(cases)("%j", (input, expected) => {
    expect(stripeTone(input)).toBe(expected);
  });

  it("is violet for an active emergency whatever the status, except removed", () => {
    for (const status of ["pending", "verified_true", "verified_false", "under_review"] as const) {
      expect(stripeTone({ status, emergencyActive: true })).toBe("tertiary");
    }
    expect(stripeTone({ status: "removed", emergencyActive: true })).toBeNull();
  });
});

describe("statusBadgeSpec with the pipeline's real answers (Part 9)", () => {
  it.each([
    [
      "#true",
      { status: "verified_true", verdictSource: "pipeline", confidenceScore: "95.00" },
      "VERIFIED 95%",
    ],
    [
      "#false",
      { status: "verified_false", verdictSource: "pipeline", confidenceScore: "92.00" },
      "FALSE 92%",
    ],
    [
      "#unsure",
      { status: "under_review", verdictSource: null, confidenceScore: null },
      "UNDER REVIEW",
    ],
  ] as [string, PostDisplayInput, string][])("%s", (_tag, input, label) => {
    expect(statusBadgeSpec(input)?.label).toBe(label);
  });
});
