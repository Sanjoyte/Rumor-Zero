import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import type { PostSource } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { sourceHref, sourceLabel } from "./sources";

/**
 * The one-line evidence row under a fact claim (Stitch b1's evidence drawer, cut to a single
 * line): the first source's host or `doi.org/…`, then "+N more" when there are more. The text is
 * plain and the link is `nofollow ugc` (ARCHITECTURE §4c). "+N more" links to the detail page
 * (Part 5), where every source is listed. Both links sit above the card's stretched link.
 */
export function SourceLink({
  sources,
  moreHref,
  className,
}: {
  sources: PostSource[];
  /** Part 5: where "+N more" goes, the sources list on the detail page (`/p/{id}#sources`). */
  moreHref?: string;
  className?: string;
}) {
  if (sources.length === 0) return null;
  const [first, ...others] = sources;
  const href = sourceHref(first);
  const label = sourceLabel(first);
  return (
    <div
      className={cn(
        "flex items-center gap-space-sm rounded-lg border border-outline-variant/30 bg-surface-container-low/70 px-space-md py-space-sm font-body-sm text-body-sm",
        className,
      )}
    >
      <Icon name="link" size="lg" className="shrink-0 text-outline" />
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="nofollow ugc noopener noreferrer"
          title={first.value}
          className="relative z-10 flex min-w-0 items-center gap-space-xs font-label-code text-label-code font-semibold text-secondary hover:underline"
        >
          <span className="truncate">{label}</span>
          <Icon name="open_in_new" size="sm" className="shrink-0" />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      ) : (
        <span title={first.value} className="min-w-0 truncate font-label-code text-label-code">
          {label}
        </span>
      )}
      {others.length > 0 &&
        (moreHref ? (
          <Link
            href={moreHref}
            prefetch={false}
            className="relative z-10 shrink-0 font-label-code text-label-badge font-semibold tracking-wider text-secondary hover:underline"
          >
            +{others.length} more
          </Link>
        ) : (
          <span className="shrink-0 font-label-code text-label-badge font-semibold tracking-wider text-outline">
            +{others.length} more
          </span>
        ))}
    </div>
  );
}
