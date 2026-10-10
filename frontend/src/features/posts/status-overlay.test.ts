import { describe, expect, it } from "vitest";
import type { PostStatusUpdate } from "@/lib/api/types";
import { applyStatus, pendingPostIds } from "./status-overlay";
import { feedEntry, makePost, repostEntry, unavailableEntry } from "./test-helpers";

const update = (over: Partial<PostStatusUpdate> = {}): PostStatusUpdate => ({
  id: "p1",
  status: "verified_true",
  confidence_score: "94.00",
  verdict_source: "pipeline",
  ...over,
});

describe("applyStatus", () => {
  const post = makePost({ id: "p1", post_type: "fact", status: "pending" });

  it("returns the very same post when nothing was polled", () => {
    expect(applyStatus(post, {})).toBe(post);
    expect(applyStatus(post, { other: update({ id: "other" }) })).toBe(post);
  });

  it("lays the polled status, confidence and source over the post", () => {
    expect(applyStatus(post, { p1: update() })).toEqual({
      ...post,
      status: "verified_true",
      confidence_score: "94.00",
      verdict_source: "pipeline",
    });
  });

  it("returns the same post when the poll agrees with it", () => {
    const same = update({ status: "pending", confidence_score: null, verdict_source: null });
    expect(applyStatus(post, { p1: same })).toBe(post);
  });

  it("can turn a post into a removed one", () => {
    const removed = applyStatus(post, {
      p1: update({ status: "removed", confidence_score: null, verdict_source: null }),
    });
    expect(removed.status).toBe("removed");
  });
});

describe("pendingPostIds", () => {
  const pendingFact = (id: string) => makePost({ id, post_type: "fact", status: "pending" });

  it("lists the posts loaded as pending, in order, and skips everything else", () => {
    const items = [
      feedEntry(pendingFact("a")),
      feedEntry(makePost({ id: "b" })),
      feedEntry(makePost({ id: "c", post_type: "fact", status: "verified_true" })),
      feedEntry(pendingFact("d")),
    ];
    expect(pendingPostIds(items)).toEqual(["a", "d"]);
  });

  it("polls the original of a repost: it shows the original's live label", () => {
    expect(pendingPostIds([repostEntry(pendingFact("e"))])).toEqual(["e"]);
  });

  it("skips a repost whose original is gone, and settled ones", () => {
    const items = [
      unavailableEntry("x"),
      repostEntry(makePost({ id: "y", post_type: "fact", status: "verified_true" })),
    ];
    expect(pendingPostIds(items)).toEqual([]);
  });

  it("asks about a post once, however many items show it", () => {
    const items = [feedEntry(pendingFact("a")), repostEntry(pendingFact("a"))];
    expect(pendingPostIds(items)).toEqual(["a"]);
  });
});
