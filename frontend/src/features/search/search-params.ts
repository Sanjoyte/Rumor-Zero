/** The search page's state lives in the address: `?q=&type=posts|users&filter=…` (Part 12). */

export const MAX_QUERY_LENGTH = 200;

export type SearchType = "posts" | "users";
export type SearchFilter = "all" | "facts" | "opinions" | "verified" | "false" | "review";

export interface SearchState {
  q: string;
  type: SearchType;
  filter: SearchFilter;
}

export const SEARCH_FILTERS: readonly SearchFilter[] = [
  "all",
  "facts",
  "opinions",
  "verified",
  "false",
  "review",
];

/** What each chip sends to `GET /api/v1/search/` besides `q` (the filters are ANDed server-side). */
export const FILTER_PARAMS: Record<SearchFilter, Record<string, string>> = {
  all: {},
  facts: { post_type: "fact" },
  opinions: { post_type: "opinion" },
  verified: { status: "verified_true" },
  false: { status: "verified_false" },
  review: { status: "under_review" },
};

/**
 * The state from the address. Anything unknown falls back to the default (Posts, All); a repeated
 * key reads its first value; the query is trimmed and cut at 200 characters (the API's limit), and
 * People has no chips.
 */
export function parseSearchParams(params: { get(name: string): string | null }): SearchState {
  const q = (params.get("q") ?? "").trim().slice(0, MAX_QUERY_LENGTH);
  const type: SearchType = params.get("type") === "users" ? "users" : "posts";
  const raw = params.get("filter");
  const filter = SEARCH_FILTERS.find((candidate) => candidate === raw) ?? "all";
  return { q, type, filter: type === "users" ? "all" : filter };
}

/** The address for a state, leaving out what is the default. */
export function searchHref({ q, type, filter }: SearchState): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (type === "users") params.set("type", "users");
  else if (filter !== "all") params.set("filter", filter);
  const query = params.toString();
  return query ? `/search?${query}` : "/search";
}
