import { describe, expect, it } from "vitest";
import { emptyDraft, isEmptyDraft, newRow } from "./draft";

describe("draft", () => {
  it("starts empty with no type chosen and one source row", () => {
    const draft = emptyDraft();
    expect(draft.content).toBe("");
    expect(draft.postType).toBeNull();
    expect(draft.rows).toHaveLength(1);
    expect(draft.rows[0].text).toBe("");
    expect(isEmptyDraft(draft)).toBe(true);
  });

  it("gives every row its own id", () => {
    const ids = new Set([newRow().id, newRow().id, ...emptyDraft().rows.map((r) => r.id)]);
    expect(ids.size).toBe(3);
  });

  it("is no longer empty after typing, choosing a type or filling a row", () => {
    expect(isEmptyDraft({ ...emptyDraft(), content: "x" })).toBe(false);
    expect(isEmptyDraft({ ...emptyDraft(), postType: "fact" })).toBe(false);
    expect(isEmptyDraft({ ...emptyDraft(), rows: [newRow("10.1/x")] })).toBe(false);
  });
});
