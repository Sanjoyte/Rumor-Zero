import type { FactQuota } from "@/lib/api/types";

export interface QuotaLine {
  /** "7/10", set in bold; null when the line is only text (paused). */
  count: string | null;
  text: string;
  /** "next at 14:05" when nothing is left. */
  suffix: string | null;
  tone: "normal" | "empty";
}

interface Options {
  now?: Date;
  /** IANA zone; the viewer's own by default. Tests pass "UTC". */
  timeZone?: string;
}

function dayKey(date: Date, timeZone?: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone }).format(date);
}

/** "next at 14:05", or "next tomorrow at 02:10" when it isn't today (viewer's time). */
export function formatNextSlot(iso: string, { now = new Date(), timeZone }: Options = {}): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "";
  const time = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  }).format(when);
  const sameDay = dayKey(when, timeZone) === dayKey(now, timeZone);
  return sameDay ? `next at ${time}` : `next tomorrow at ${time}`;
}

/** The composer footer's allowance line (Stitch b2, user decision 2026-10-08: rolling 24 h). */
export function quotaLine(quota: FactQuota | null, options: Options = {}): QuotaLine | null {
  if (!quota) return null;
  if (quota.limit === 0) {
    return { count: null, text: "Fact posts are paused right now", suffix: null, tone: "empty" };
  }
  const count = `${quota.remaining}/${quota.limit}`;
  if (quota.remaining > 0) {
    return { count, text: "fact posts left", suffix: null, tone: "normal" };
  }
  const suffix = quota.next_slot_at ? formatNextSlot(quota.next_slot_at, options) : null;
  return { count, text: "fact posts left", suffix: suffix || null, tone: "empty" };
}
