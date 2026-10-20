/** Shared test helpers for the credibility widgets (not shipped: only *.test.* files import it). */
import type { LedgerEntry, ReputationSummary, TrendPoint } from "@/lib/api/types";

/** `n` UTC days ending on `last`, one point each, scores from `first` to `last` in a straight run. */
export function makeTrend(first = 60, last = 68, end = "2026-10-20", n = 30): TrendPoint[] {
  const stop = new Date(`${end}T00:00:00Z`).getTime();
  return Array.from({ length: n }, (_, i) => ({
    date: new Date(stop - (n - 1 - i) * 86_400_000).toISOString().slice(0, 10),
    score: Math.round(first + ((last - first) * i) / (n - 1)),
  }));
}

export function makeSummary(overrides: Partial<ReputationSummary> = {}): ReputationSummary {
  return {
    score: 68,
    sample: 23,
    verified: 20,
    false: 3,
    removed: 0,
    recent: [],
    trend: makeTrend(),
    ...overrides,
  };
}

let counter = 0;

export function makeEntry(overrides: Partial<LedgerEntry> = {}): LedgerEntry {
  counter += 1;
  return {
    id: `e-${counter}`,
    kind: "fact_true",
    label: "Fact verified true",
    positive: "1.00",
    negative: "0.00",
    score_after: 62,
    created_at: "2026-10-12T09:30:00Z",
    post_id: `00000000-0000-4000-8000-00000000000${counter % 10}`,
    reverses: null,
    reversed: false,
    appeal: null,
    ...overrides,
  };
}
