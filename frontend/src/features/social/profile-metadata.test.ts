import { describe, expect, it } from "vitest";
import { OG_IMAGES, TWITTER_IMAGES } from "@/features/posts/post-metadata";
import { bioExcerpt, profileMetadata } from "./profile-metadata";
import { makeProfile } from "./test-helpers";

const found = (overrides = {}) => ({ kind: "found" as const, profile: makeProfile(overrides) });

describe("bioExcerpt", () => {
  it("collapses whitespace and cuts a long bio at a word", () => {
    expect(bioExcerpt("  one \n two  ")).toBe("one two");
    const long = "word ".repeat(80);
    const cut = bioExcerpt(long);
    expect(Array.from(cut).length).toBeLessThanOrEqual(161);
    expect(cut.endsWith("…")).toBe(true);
    expect(cut).not.toMatch(/\s…$/);
  });
});

describe("profileMetadata", () => {
  it("titles a named profile 'Name (@user)' and uses the bio as the description", () => {
    const meta = profileMetadata("bob", found());
    expect(meta.title).toBe("Bob Stone (@bob)");
    expect(meta.description).toBe("Counting things.");
    expect(meta.alternates?.canonical).toBe("/u/bob");
    expect(meta.robots).toBeUndefined();
  });

  it("shows '@user' once when the display name is blank, and a default description without a bio", () => {
    const meta = profileMetadata("bob", found({ display_name: "  ", bio: "" }));
    expect(meta.title).toBe("@bob");
    expect(meta.description).toBe("Posts by @bob on Rumor Zero.");
  });

  it("sets the whole openGraph and twitter objects, images included (a page-level one replaces the root's)", () => {
    const meta = profileMetadata("bob", found());
    expect(meta.openGraph).toMatchObject({
      type: "profile",
      siteName: "Rumor Zero",
      title: "Bob Stone (@bob) · Rumor Zero",
      url: "/u/bob",
      images: OG_IMAGES,
    });
    expect(meta.twitter).toMatchObject({
      card: "summary_large_image",
      title: "Bob Stone (@bob) · Rumor Zero",
      images: TWITTER_IMAGES,
    });
    // The names live in post-metadata.ts (the brand guard allows only it); here, that they are set.
    expect(OG_IMAGES[0]).toMatchObject({ width: 1200, height: 630 });
    expect(meta.openGraph?.images).toHaveLength(1);
    expect(meta.twitter?.images).toHaveLength(1);
  });

  it("uses the canonical lower-case name from the server", () => {
    const meta = profileMetadata("BOB", found());
    expect(meta.alternates?.canonical).toBe("/u/bob");
  });

  it("keeps a missing profile out of the index", () => {
    const meta = profileMetadata("Nobody", { kind: "not-found" });
    expect(meta.title).toBe("Profile not found");
    expect(meta.robots).toEqual({ index: false, follow: false });
    expect(meta.alternates?.canonical).toBe("/u/nobody");
  });

  it("falls back to generic tags, still indexable, when the server read failed", () => {
    const meta = profileMetadata("bob", { kind: "unavailable" });
    expect(meta.title).toBe("@bob");
    expect(meta.robots).toBeUndefined();
    expect(meta.openGraph).toMatchObject({ images: OG_IMAGES });
  });
});
