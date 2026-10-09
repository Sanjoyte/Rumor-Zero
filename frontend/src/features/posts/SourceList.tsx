import { Card } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";
import type { PostSource } from "@/lib/api/types";
import { sourceHref } from "./sources";

/**
 * Every source of a fact post (Stitch b3's primary-sources registry, without its sample titles,
 * org chips, "% match" and archive lines): numbered 01, 02 … in the order entered, each with its
 * full stored value (hosts are already punycode) and an open-in-new link. A DOI links to
 * doi.org. The text is plain; links carry `rel="nofollow ugc noopener noreferrer"`.
 */
export function SourceList({ sources }: { sources: PostSource[] }) {
  return (
    <section
      id="sources"
      aria-labelledby="sources-heading"
      className="flex scroll-mt-20 flex-col gap-space-md"
    >
      <h2 id="sources-heading" className="font-headline-sm text-headline-sm text-on-surface">
        Sources ({sources.length})
      </h2>
      {sources.length === 0 ? (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          The author didn&apos;t add any sources.
        </p>
      ) : (
        <Card as="div" className="p-space-md">
          <ol className="flex flex-col gap-space-sm">
            {sources.map((source, index) => {
              const number = String(index + 1).padStart(2, "0");
              const href = sourceHref(source);
              return (
                <li
                  key={`${index}:${source.value}`}
                  className="flex items-start justify-between gap-space-md rounded-lg border border-outline-variant/30 bg-surface-container-low p-space-md"
                >
                  <div className="flex min-w-0 items-start gap-space-md">
                    <span className="mt-0.5 font-label-code text-label-code font-bold text-outline">
                      {number}
                    </span>
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="font-label-code text-label-badge tracking-wider text-outline uppercase">
                        {source.kind === "doi" ? "DOI" : "Link"}
                      </span>
                      <span className="font-body-md text-body-md font-semibold break-words text-on-surface">
                        {source.value}
                      </span>
                    </div>
                  </div>
                  {href && (
                    <a
                      href={href}
                      target="_blank"
                      rel="nofollow ugc noopener noreferrer"
                      aria-label={`Open source ${number} in a new tab`}
                      className="shrink-0 rounded-lg p-space-xs text-outline transition-colors hover:text-secondary"
                    >
                      <Icon name="open_in_new" size="xl" />
                    </a>
                  )}
                </li>
              );
            })}
          </ol>
        </Card>
      )}
    </section>
  );
}
