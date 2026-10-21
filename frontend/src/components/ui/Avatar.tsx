"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";

/** Sizes are Tailwind spacing units (6 = 24px ... 20 = 80px), matching Stitch. */
const SIZE = {
  6: { box: "h-6 w-6 font-label-code text-label-badge font-bold", px: 24 },
  8: { box: "h-8 w-8 font-label-code text-label-code", px: 32 },
  10: { box: "h-10 w-10 font-label-code text-label-code", px: 40 },
  14: { box: "h-14 w-14 font-headline-sm text-headline-sm tracking-wider", px: 56 },
  20: { box: "h-20 w-20 font-headline-sm text-headline-sm tracking-wider", px: 80 },
} as const;

export type AvatarSize = keyof typeof SIZE;

/**
 * First letters of the first two words, or the first two characters of a single word. A handle
 * ("@ada", the fallback for a blank display name) loses its "@".
 */
export function initialsFor(name: string): string {
  const words = name.trim().replace(/^@/, "").split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return Array.from(words[0]).slice(0, 2).join("").toUpperCase();
  return (Array.from(words[0])[0] + Array.from(words[1])[0]).toUpperCase();
}

export interface AvatarProps {
  name: string;
  /** The profile photo (Part 14B). Without it, or when it fails to load, initials are shown. */
  src?: string | null;
  size?: AvatarSize;
  /** Set when the name is written next to the avatar, so it is not announced twice. */
  decorative?: boolean;
  className?: string;
}

export function Avatar({ name, src, size = 10, decorative, className }: AvatarProps) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const { box, px } = SIZE[size];
  const showPhoto = Boolean(src) && failedSrc !== src;

  if (showPhoto && src) {
    return (
      // A plain img on purpose: next/image optimisation is not used on Workers (ARCHITECTURE 10).
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={decorative ? "" : name}
        width={px}
        height={px}
        // Each photo is one Worker request per browser (ARCHITECTURE 13): off-screen avatars in a
        // long feed shouldn't load until they scroll near.
        loading="lazy"
        decoding="async"
        onError={() => setFailedSrc(src)}
        // The server-rendered image can fail before React attaches onError. Catch that case here:
        // a finished image with no width is a broken one.
        ref={(node) => {
          if (node?.complete && node.naturalWidth === 0) setFailedSrc(src);
        }}
        className={cn(
          "shrink-0 rounded-full border border-outline-variant/40 object-cover",
          box.split(" ").slice(0, 2).join(" "),
          className,
        )}
      />
    );
  }

  return (
    <span
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : name}
      aria-hidden={decorative ? true : undefined}
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-inverse-surface text-inverse-on-surface",
        box,
        className,
      )}
    >
      {initialsFor(name)}
    </span>
  );
}
