import type { AppealStatus } from "@/lib/api/types";

/** The words of Part 11D's credibility widget and panel. */
export const CREDIBILITY_COPY = {
  widgetHeading: "Credibility",
  panelHeading: "Your credibility history",
  lastThirtyDays: "Last 30 days",
  hiddenNote: "Others see New until 3 of your posts are checked.",
  empty: "Your record appears here once one of your posts is checked.",
  emptyTitle: "No credibility history yet",
  loadFailed: "Couldn't load your credibility history. Check your connection and try again.",
  reversed: "Reversed",
  askAgain: "Ask for another look",
  viewPost: "View post",
  end: "That is your whole history.",
} as const;

/** What an appeal that already exists says, in words (a link to the post would go nowhere new). */
export const APPEAL_STATE_WORDS: Record<AppealStatus, string> = {
  open: "Appeal open",
  upheld: "Appeal upheld — the decision stands",
  overturned: "Appeal overturned",
};

/** The one-sentence text alternative of the sparkline: where the line starts and ends. */
export function trendSummary(first: number, last: number): string {
  if (first === last) return `Credibility stayed at ${last} over the last 30 days.`;
  return `Credibility ${last > first ? "rose" : "fell"} from ${first} to ${last} over the last 30 days.`;
}
