/**
 * The platform defaults the help pages quote (ARCHITECTURE §3 and §4a). Moderators can change the
 * editable ones in Django Admin; the pages state the defaults and say so. `numbers.test.ts` pins
 * each value to the architecture document, so a change there fails a test here.
 */
export const INFO_NUMBERS = {
  reportThreshold: 5,
  reportWindowHours: 24,
  reportMinAccountAgeHours: 24,
  emergencyReportThreshold: 2,
  confidenceThreshold: 85,
  factPostsPerDay: 10,
  emergencyDurationHours: 24,
  emergencyPostsPerDay: 1,
  emergencyMinAccountAgeDays: 7,
  emergencyMinReputation: 40,
  emergencyFalseCooldownDays: 30,
  sourcesPerFact: 5,
  scoreStart: 50,
  scoreImaginaryEvents: 10,
  scorePublicAfter: 3,
  reporterCreditCap: 4,
  reporterCreditWindowDays: 30,
} as const;

/** One row of the credibility table (ARCHITECTURE §4a): the same kinds and weights as the ledger. */
export interface ScoreEvent {
  kind: string;
  who: string;
  when: string;
  effect: string;
}

export const SCORE_EVENTS: readonly ScoreEvent[] = [
  {
    kind: "fact_true",
    who: "The author",
    when: "Their fact post is verified TRUE, by the checks or by a moderator.",
    effect: "Raises the score: +1 positive event.",
  },
  {
    kind: "fact_false",
    who: "The author",
    when: "Their fact post is marked FALSE.",
    effect: "Lowers the score: +1 negative event.",
  },
  {
    kind: "emergency_false",
    who: "The author",
    when: "Their emergency post is marked FALSE (this replaces fact_false).",
    effect: "Lowers the score more: +3 negative events.",
  },
  {
    kind: "post_removed",
    who: "The author",
    when: "A moderator removes the post, whether it was a fact or an opinion. It adds to the label's event.",
    effect: "Lowers the score: +2 negative events.",
  },
  {
    kind: "report_upheld",
    who: "The reporter",
    when: "A moderator removes a post you reported, or marks it FALSE for the first time, while your report is open.",
    effect: `Raises the score a little: +0.25 positive. At most ${INFO_NUMBERS.reporterCreditCap} credits in any ${INFO_NUMBERS.reporterCreditWindowDays} days.`,
  },
  {
    kind: "repost_true",
    who: "Someone who reposted",
    when: "You reposted a fact while it was still being checked or reviewed, and it ends TRUE.",
    effect: "Raises the score a little: +0.25 positive.",
  },
  {
    kind: "repost_false",
    who: "Someone who reposted",
    when: "The same, and it ends FALSE.",
    effect: "Lowers the score: +0.5 negative.",
  },
  {
    kind: "repost_emergency_false",
    who: "Someone who reposted",
    when: "The same, and it was an emergency that ends FALSE.",
    effect: "Lowers the score: +1 negative.",
  },
  {
    kind: "repost_removed",
    who: "Someone who reposted",
    when: "The same, and a moderator removes the post.",
    effect: "Lowers the score: +0.5 negative.",
  },
  {
    kind: "reversal",
    who: "Whoever the cancelled event belonged to",
    when: "An appeal or a review overturns the outcome.",
    effect: "Cancels that event exactly, so the score goes back to what it would have been.",
  },
] as const;
