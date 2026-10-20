import type { Metadata } from "next";
import { Suspense } from "react";
import { SearchPage, SearchSkeleton } from "@/features/search/SearchPage";

// A fixed title and no index: a results page is for the person who searched. The page stays
// static (the client reads `?q=`), so a query, tab or chip change costs no Worker request.
export const metadata: Metadata = { title: "Search", robots: { index: false, follow: true } };

export default function Page() {
  return (
    <Suspense fallback={<SearchSkeleton />}>
      <SearchPage />
    </Suspense>
  );
}
