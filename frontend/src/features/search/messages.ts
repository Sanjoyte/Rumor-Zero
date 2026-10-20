/** What the search page says (Part 12). Failures of the list itself come from the shared helpers. */
export const SEARCH_MESSAGES = {
  promptTitle: "Search Rumor Zero",
  promptBody: "Type a word or a phrase to find posts, or a name to find people.",
  noPostsTitle: (q: string) => `No results for “${q}”`,
  noPostsBody: "Try different words or remove a filter.",
  noPeopleTitle: (q: string) => `No people found for “${q}”`,
  noPeopleBody: "Try a different name or the start of a username.",
  capped: "That's the first 100 results. Try more specific words to narrow them down.",
  caughtUp: "You're caught up.",
  everyone: "That's everyone.",
  morePeopleFailed: "Couldn't load more people.",
  tip: "Tip: use quotes for an exact phrase, a minus sign to leave a word out, and or for either word.",
} as const;

/** Search stops after five pages of twenty (ARCHITECTURE §9). */
export const SEARCH_RESULT_CAP = 100;
