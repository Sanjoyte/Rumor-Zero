const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "now", "5m", "3h", "2d", then "Sep 30" (same year) or "Sep 30, 2025". UTC, like the backend. */
export function formatRelativeTime(value: string | Date, now: Date = new Date()): string {
  const then = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(then.getTime())) return "";
  const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);
  if (seconds < MINUTE) return "now";
  if (seconds < HOUR) return `${Math.floor(seconds / MINUTE)}m`;
  if (seconds < DAY) return `${Math.floor(seconds / HOUR)}h`;
  if (seconds < 7 * DAY) return `${Math.floor(seconds / DAY)}d`;
  const sameYear = then.getUTCFullYear() === now.getUTCFullYear();
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: sameYear ? undefined : "numeric",
    timeZone: "UTC",
  }).format(then);
}

/**
 * "Oct 9, 2026, 2:05 PM UTC": the detail page's exact time. Always UTC, so the server render and
 * the browser print the same text (no hydration mismatch) whatever the viewer's time zone.
 */
export function formatFullDateTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "";
  const text = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(date);
  return `${text} UTC`;
}

/** "March 2024": when someone joined. UTC, so the server render and the browser agree. */
export function formatMonthYear(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

/** A profile counter in full with a thousands separator, as Stitch shows it: 1420 becomes "1,420". */
export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

/** 999 becomes "999", 1200 becomes "1.2K", 3400000 becomes "3.4M". */
export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(
    value,
  );
}

/** The API sends confidence as a decimal string ("94.00"); the badge shows "94%". */
export function formatConfidence(score: string | number | null | undefined): string {
  if (score === null || score === undefined || score === "") return "";
  const n = typeof score === "number" ? score : Number(score);
  return Number.isFinite(n) ? `${Math.round(n)}%` : "";
}

/**
 * Characters as the server counts them: code points, so an emoji is 1 (Python's `len` and
 * Postgres's `char_length`), not the 2 UTF-16 units `string.length` reports.
 */
export function countCharacters(text: string): number {
  return Array.from(text).length;
}
