import { describe, expect, it } from "vitest";
import type { PublicPostResult } from "@/lib/api/server";
import { excerpt, postMetadata } from "./post-metadata";
import { makePost } from "./test-helpers";

const ID = "11111111-1111-4111-8111-111111111111";
const found = (overrides = {}): PublicPostResult => ({
  kind: "found",
  post: makePost({ id: ID, ...overrides }),
});

describe("excerpt", () => {
  it("keeps a short claim whole, with its whitespace collapsed", () => {
    expect(excerpt("  Rain \n is   nice ")).toBe("Rain is nice");
  });

  it("cuts a long claim at a word and adds an ellipsis", () => {
    const text =
      "Solar capacity grew by thirty percent worldwide last year according to the agency";
    const short = excerpt(text);
    expect(short).toBe("Solar capacity grew by thirty percent worldwide last year according…");
    expect(Array.from(short).length).toBeLessThanOrEqual(71);
  });

  it("cuts mid-word when there is no space to cut at, and counts code points", () => {
    const text = "😀".repeat(100);
    expect(excerpt(text)).toBe(`${"😀".repeat(70)}…`);
  });

  it("drops trailing punctuation before the ellipsis", () => {
    expect(excerpt(`${"word ".repeat(13)}end, and more words after that`)).not.toMatch(/[,.;:]…$/);
  });
});

describe("postMetadata", () => {
  it("titles the page with the excerpt and describes it with the type and status label", () => {
    const meta = postMetadata(
      ID,
      found({
        post_type: "fact",
        status: "verified_true",
        verdict_source: "pipeline",
        confidence_score: "94.00",
        content: "Rain is wet",
      }),
    );
    expect(meta.title).toBe("Rain is wet"); // the root template adds " · Rumor Zero"
    expect(meta.description).toBe("Fact · VERIFIED 94%");
    expect(meta.alternates).toEqual({ canonical: `/p/${ID}` });
    expect(meta.robots).toBeUndefined();
  });

  it("says CHECKING FACTS… for a pending fact, UNDER REVIEW and FALSE · REVIEWED likewise", () => {
    expect(postMetadata(ID, found({ post_type: "fact", status: "pending" })).description).toBe(
      "Fact · CHECKING FACTS…",
    );
    expect(postMetadata(ID, found({ post_type: "fact", status: "under_review" })).description).toBe(
      "Fact · UNDER REVIEW",
    );
    expect(
      postMetadata(
        ID,
        found({ post_type: "fact", status: "verified_false", verdict_source: "moderator" }),
      ).description,
    ).toBe("Fact · FALSE · REVIEWED");
  });

  it("describes an opinion as just Opinion", () => {
    expect(postMetadata(ID, found()).description).toBe("Opinion");
  });

  it("sets Open Graph and Twitter tags in full, because a page-level object replaces the root's", () => {
    const meta = postMetadata(ID, found({ content: "Rain is wet" }));
    expect(meta.openGraph).toMatchObject({
      type: "article",
      siteName: "Rumor Zero",
      title: "Rain is wet · Rumor Zero", // OG titles don't get the template
      description: "Opinion",
      url: `/p/${ID}`,
      images: [{ url: "/opengraph-image.png", width: 1200, height: 630, alt: "Rumor Zero" }],
    });
    expect(meta.twitter).toMatchObject({
      card: "summary_large_image",
      title: "Rain is wet · Rumor Zero",
      images: [{ url: "/twitter-image.png", alt: "Rumor Zero" }],
    });
  });

  it("keeps a removed post out of search and out of the tags", () => {
    const meta = postMetadata(ID, found({ status: "removed", content: "" }));
    expect(meta.title).toBe("Removed post");
    expect(meta.description).toBe("This post was removed by a moderator.");
    expect(meta.robots).toEqual({ index: false, follow: false });
    expect(JSON.stringify(meta)).not.toContain("Opinion");
  });

  it("is noindex for a post that doesn't exist", () => {
    const meta = postMetadata(ID, { kind: "not-found" });
    expect(meta.title).toBe("Post not found");
    expect(meta.robots).toEqual({ index: false, follow: false });
  });

  it("falls back to generic tags, still indexable, when the server couldn't read the post", () => {
    const meta = postMetadata(ID, { kind: "unavailable" });
    expect(meta.title).toBe("Post");
    expect(meta.robots).toBeUndefined();
    expect(meta.openGraph).toMatchObject({ siteName: "Rumor Zero", title: "Post · Rumor Zero" });
  });
});
