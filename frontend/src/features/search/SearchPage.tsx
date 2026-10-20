"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterChips, type FilterChip } from "@/components/ui/FilterChips";
import { Skeleton } from "@/components/ui/Skeleton";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { SEARCH_MESSAGES } from "./messages";
import { PeopleResults } from "./PeopleResults";
import { PostResults } from "./PostResults";
import { SearchBar } from "./SearchBar";
import { parseSearchParams, searchHref, type SearchFilter, type SearchType } from "./search-params";

const PREFIX = "search";
const TABS = [
  { id: "posts", label: "Posts" },
  { id: "users", label: "People" },
];
// Stitch b4's chips: the dots are the status colours, Opinions the neutral one.
const CHIPS: FilterChip[] = [
  { id: "all", label: "All" },
  { id: "facts", label: "Facts" },
  { id: "opinions", label: "Opinions", dot: "outline-variant" },
  { id: "verified", label: "Verified", dot: "primary" },
  { id: "false", label: "FALSE", dot: "error" },
  { id: "review", label: "Under review", dot: "verdict-review" },
];

export const SEARCH_CONTAINER =
  "mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg";

/** What the page shows while the address is read (the route's Suspense fallback). */
export function SearchSkeleton() {
  return (
    <div className={SEARCH_CONTAINER} aria-busy="true">
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

/**
 * `/search` (Stitch b4): the query box, the Posts and People tabs, the filter chips and the
 * results. The address is the whole state (`?q=&type=&filter=`), so tabs, chips and back/forward
 * just work: a tab is a push, a chip a replace, a new query a form submit. Not built from b4:
 * result counts, the sort menu, Primary Sources, the claim-data box and the contributor spotlight
 * (ANALYSIS b-3). With no query nothing is requested.
 */
export function SearchPage() {
  const router = useRouter();
  const state = parseSearchParams(useSearchParams());
  const { q, type, filter } = state;

  function chooseTab(id: string) {
    if (id !== type) router.push(searchHref({ q, type: id as SearchType, filter: "all" }));
  }
  function chooseFilter(selected: string[]) {
    // A pressed chip toggles off: that means "All".
    router.replace(searchHref({ q, type, filter: (selected[0] ?? "all") as SearchFilter }));
  }

  return (
    <div className={SEARCH_CONTAINER}>
      <h1 className="sr-only">Search</h1>
      <section className="space-y-space-md rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-space-lg shadow-sm">
        <SearchBar q={q} type={type} filter={filter} />
        <hr className="border-outline-variant/30" />
        <Tabs tabs={TABS} value={type} onChange={chooseTab} label="Search in" idPrefix={PREFIX} />
        {type === "posts" && (
          <FilterChips
            label="Filter posts"
            chips={CHIPS}
            selected={[filter]}
            onChange={chooseFilter}
            className="pt-space-xs"
          />
        )}
      </section>
      <TabPanel idPrefix={PREFIX} tab={type} selected>
        {q === "" ? (
          <EmptyState icon="search" title={SEARCH_MESSAGES.promptTitle}>
            {SEARCH_MESSAGES.promptBody}
          </EmptyState>
        ) : type === "posts" ? (
          <PostResults key={`posts:${filter}:${q}`} q={q} filter={filter} />
        ) : (
          <PeopleResults key={`users:${q}`} q={q} />
        )}
      </TabPanel>
    </div>
  );
}
