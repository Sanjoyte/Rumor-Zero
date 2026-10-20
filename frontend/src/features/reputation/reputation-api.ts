/** The credibility endpoints (ARCHITECTURE §9). */
import { api } from "@/lib/api/client";
import type { CursorPage, LedgerEntry, ReputationSummary } from "@/lib/api/types";
import { withCursor } from "@/features/social/social-api";

export const REPUTATION_PATHS = {
  user: (username: string) => `/v1/users/${encodeURIComponent(username)}/reputation/`,
  myEvents: "/v1/me/reputation/events/",
} as const;

/** An account's public credibility summary, with the 30-day trend. Public: it never sends the token. */
export function fetchReputation(
  username: string,
  signal?: AbortSignal,
): Promise<ReputationSummary> {
  return api.get<ReputationSummary>(REPUTATION_PATHS.user(username), { signal, token: false });
}

export interface LedgerPage {
  items: LedgerEntry[];
  nextCursor: string | null;
}

/** One page of your own ledger, newest first, reversal rows included. */
export async function fetchMyReputationEvents(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<LedgerPage> {
  const body = await api.get<CursorPage<LedgerEntry>>(
    withCursor(REPUTATION_PATHS.myEvents, cursor),
    {
      signal,
    },
  );
  return { items: body.results, nextCursor: body.next_cursor };
}
