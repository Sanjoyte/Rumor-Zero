import assets from "@/lib/brand-assets.json";
import { cn } from "@/lib/cn";

/** Rendered heights in px (ARCHITECTURE 14): sm 24, md 36, lg 48. */
const HEIGHT = { sm: 24, md: 36, lg: 48 } as const;

export type LogoSize = keyof typeof HEIGHT;
export type LogoVariant = "wordmark" | "mark";

export interface LogoProps {
  /** `wordmark` is the full logo; `mark` is the "0" alone (tablet icon dock). */
  variant?: LogoVariant;
  size?: LogoSize;
  /** Set when "Rumor Zero" is written next to the logo, so it is not announced twice. */
  decorative?: boolean;
  className?: string;
}

/**
 * The only way the UI shows the brand. The files and their proportions come from
 * `brand-assets.json`, which `npm run brand:build` generates from design/logo.svg.
 */
export function Logo({ variant = "wordmark", size = "md", decorative, className }: LogoProps) {
  const asset = variant === "mark" ? assets.mark : assets.wordmark;
  const height = HEIGHT[size];
  const width = Math.round((height * asset.width) / asset.height);

  return (
    // A plain img on purpose: the SVG is never inlined, and next/image optimisation is not used
    // on Workers (ARCHITECTURE 10 and 14). Width and height are set, so nothing shifts on load.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={asset.src}
      alt={decorative ? "" : assets.alt}
      width={width}
      height={height}
      className={cn("block shrink-0", className)}
    />
  );
}
