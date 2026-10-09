/**
 * The head of `/p/[id]` (ARCHITECTURE §10, ANALYSIS c-35): title, description, Open Graph and
 * Twitter tags, and the canonical link. A page-level `openGraph` or `twitter` replaces the root
 * layout's whole object (Next doesn't merge it), so the site name, the type and the static share
 * images are set here again, and Open Graph titles don't get the title template: the suffix is
 * added by hand. Pure, so the whole table is unit-tested.
 */
import type { Metadata } from "next";
import type { PublicPostResult } from "@/lib/api/server";
import { statusBadgeSpec } from "@/lib/post-display";

export const SITE_NAME = "Rumor Zero";
const FALLBACK_DESCRIPTION =
  "Text-only posts, labelled Opinion or Fact, with facts checked before you rely on them.";
const REMOVED_DESCRIPTION = "This post was removed by a moderator.";
const EXCERPT_LENGTH = 70;

/** The first words of a claim for a title: whitespace collapsed, cut at a word, "…" when cut. */
export function excerpt(content: string): string {
  const text = content.replace(/\s+/g, " ").trim();
  const chars = Array.from(text);
  if (chars.length <= EXCERPT_LENGTH) return text;
  const head = chars.slice(0, EXCERPT_LENGTH).join("");
  const space = head.lastIndexOf(" ");
  const cut = space >= EXCERPT_LENGTH / 2 ? head.slice(0, space) : head;
  return `${cut.replace(/[\s.,;:!?-]+$/, "")}…`;
}

function share(id: string, title: string, description: string, noindex: boolean): Metadata {
  const fullTitle = `${title} · ${SITE_NAME}`;
  return {
    title,
    description,
    alternates: { canonical: `/p/${id}` },
    openGraph: {
      type: "article",
      siteName: SITE_NAME,
      title: fullTitle,
      description,
      url: `/p/${id}`,
      images: [{ url: "/opengraph-image.png", width: 1200, height: 630, alt: SITE_NAME }],
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description,
      images: [{ url: "/twitter-image.png", alt: SITE_NAME }],
    },
    ...(noindex && { robots: { index: false, follow: false } }),
  };
}

export function postMetadata(id: string, result: PublicPostResult): Metadata {
  if (result.kind === "not-found") {
    return share(id, "Post not found", FALLBACK_DESCRIPTION, true);
  }
  if (result.kind === "unavailable") {
    return share(id, "Post", FALLBACK_DESCRIPTION, false);
  }
  const { post } = result;
  if (post.status === "removed") {
    // The server blanks a removed post for the public: nothing of it goes into the tags.
    return share(id, "Removed post", REMOVED_DESCRIPTION, true);
  }
  const badge = statusBadgeSpec({
    status: post.status,
    verdictSource: post.verdict_source,
    confidenceScore: post.confidence_score,
  });
  const type = post.post_type === "fact" ? "Fact" : "Opinion";
  const description = [type, badge?.label].filter(Boolean).join(" · ");
  return share(id, excerpt(post.content), description, false);
}
