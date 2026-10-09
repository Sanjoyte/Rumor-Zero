import { describe, expect, it } from "vitest";
import type { PostStatusUpdate } from "@/lib/api/types";
import { applyStatus, pendingPostIds } from "./status-overlay";
import { feedEntry, makePost } from "./test-helpers";

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
  it("lists the posts loaded as pending, in order, and skips everything else", () => {
    const items = [
      feedEntry(makePost({ id: "a", post_type: "fact", status: "pending" })),
      feedEntry(makePost({ id: "b" })),
      feedEntry(makePost({ id: "c", post_type: "fact", status: "verified_true" })),
      feedEntry(makePost({ id: "d", post_type: "fact", status: "pending" })),
      {
        kind: "repost" as const,
        post: makePost({ id: "e", post_type: "fact", status: "pending" }),
        reposted_by: makePost().author,
        activity_at: "2026-10-08T12:00:00Z",
      },
    ];
    expect(pendingPostIds(items)).toEqual(["a", "d"]);
  });
});
