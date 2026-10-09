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
