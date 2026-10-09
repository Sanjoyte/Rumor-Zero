/**
 * The head of `/u/[username]` (ARCHITECTURE §10): title, description, Open Graph and Twitter tags,
 * and the canonical link. As on the post page, a page-level `openGraph` or `twitter` replaces the
 * root layout's whole object, so the site name, the type, the title suffix and the static share
 * images (from `post-metadata.ts`, the one place that names them) are set here again. Pure.
 */
import type { Metadata } from "next";
import { OG_IMAGES, SITE_NAME, TWITTER_IMAGES } from "@/features/posts/post-metadata";
import type { PublicProfileResult } from "@/lib/api/server";

const BIO_EXCERPT_LENGTH = 160;

/** The first ~160 characters of a bio: whitespace collapsed, cut at a word, "…" when cut. */
export function bioExcerpt(bio: string): string {
  const text = bio.replace(/\s+/g, " ").trim();
  const chars = Array.from(text);
  if (chars.length <= BIO_EXCERPT_LENGTH) return text;
  const head = chars.slice(0, BIO_EXCERPT_LENGTH).join("");
  const space = head.lastIndexOf(" ");
  const cut = space >= BIO_EXCERPT_LENGTH / 2 ? head.slice(0, space) : head;
  return `${cut.replace(/[\s.,;:!?-]+$/, "")}…`;
}

function share(username: string, title: string, description: string, noindex: boolean): Metadata {
  const fullTitle = `${title} · ${SITE_NAME}`;
  const path = `/u/${username}`;
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      type: "profile",
      siteName: SITE_NAME,
      title: fullTitle,
      description,
      url: path,
      images: OG_IMAGES,
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description,
      images: TWITTER_IMAGES,
    },
    ...(noindex && { robots: { index: false, follow: false } }),
  };
}

export function profileMetadata(username: string, result: PublicProfileResult): Metadata {
  const name = username.toLowerCase();
  if (result.kind === "not-found") {
    return share(name, "Profile not found", `There is no account called @${name}.`, true);
  }
  if (result.kind === "unavailable") {
    return share(name, `@${name}`, `Posts by @${name} on ${SITE_NAME}.`, false);
  }
  const { profile } = result;
  const title = profile.display_name.trim()
    ? `${profile.display_name.trim()} (@${profile.username})`
    : `@${profile.username}`;
  const description = bioExcerpt(profile.bio) || `Posts by @${profile.username} on ${SITE_NAME}.`;
  return share(profile.username, title, description, false);
}
