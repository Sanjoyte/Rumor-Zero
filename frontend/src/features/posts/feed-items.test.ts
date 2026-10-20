import { describe, expect, it } from "vitest";
import { isUnavailable, visibleItems } from "./feed-items";
import { BO, feedEntry, makePost, repostEntry, unavailableEntry } from "./test-helpers";

const post = (id: string) => makePost({ id });

describe("isUnavailable", () => {
  it("tells a stub from a post", () => {
    expect(isUnavailable({ id: "x", unavailable: true })).toBe(true);
    expect(isUnavailable(post("x"))).toBe(false);
  });
});

describe("visibleItems", () => {
  it("keeps everything, in order, when nothing repeats", () => {
    const items = [feedEntry(post("a")), repostEntry(post("b")), unavailableEntry("c")];
    expect(visibleItems(items)).toEqual(items);
  });

  it("drops a post the poll found deleted, but keeps a repost of it (it shows as unavailable)", () => {
    const items = [feedEntry(post("a")), repostEntry(post("b")), feedEntry(post("b"))];
    const shown = visibleItems(items, new Set(["a", "b"]));
    expect(shown.map((i) => [i.kind, i.post.id])).toEqual([["repost", "b"]]);
  });

  it("shows a post once: a later repost of it is hidden", () => {
    const items = [feedEntry(post("a")), repostEntry(post("a")), feedEntry(post("b"))];
    expect(visibleItems(items).map((i) => [i.kind, i.post.id])).toEqual([
      ["post", "a"],
      ["post", "b"],
    ]);
  });

  it("shows a post once: the original after its repost is hidden", () => {
    const items = [repostEntry(post("a")), feedEntry(post("a"))];
    expect(visibleItems(items).map((i) => i.kind)).toEqual(["repost"]);
  });

  it("shows a post once even when two people reposted it", () => {
    const other = { ...BO, id: "u-9", username: "cy" };
    const items = [repostEntry(post("a"), BO), repostEntry(post("a"), other)];
    expect(visibleItems(items)).toHaveLength(1);
    expect(visibleItems(items)[0].reposted_by?.username).toBe("bo");
  });

  it("treats two stubs of one post as one", () => {
    const items = [unavailableEntry("a"), unavailableEntry("a", { ...BO, id: "u-9" })];
    expect(visibleItems(items)).toHaveLength(1);
  });

  it("does not change its input", () => {
    const items = [feedEntry(post("a")), repostEntry(post("a"))];
    visibleItems(items);
    expect(items).toHaveLength(2);
  });
});

describe("visibleItems: posts already shown above the list (Part 11C)", () => {
  it("hides a pinned post and a repost of it, and keeps the rest", () => {
    const items = [
      feedEntry(post("a")),
      repostEntry(post("p")),
      feedEntry(post("p")),
      feedEntry(post("b")),
    ];
    const shown = visibleItems(items, undefined, new Set(["p"]));
    expect(shown.map((item) => item.post.id)).toEqual(["a", "b"]);
  });

  it("changes nothing without the set", () => {
    const items = [feedEntry(post("a")), feedEntry(post("b"))];
    expect(visibleItems(items)).toEqual(items);
  });
});
