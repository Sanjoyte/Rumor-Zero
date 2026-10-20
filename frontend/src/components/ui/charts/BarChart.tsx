import { cn } from "@/lib/cn";
import { formatShortDate } from "@/lib/format";
import { ChartTable } from "./ChartTable";

export type BarTone = "secondary" | "outline";

const FILL: Record<BarTone, string> = {
  secondary: "bg-secondary",
  outline: "bg-outline",
};

export interface BarSeries {
  key: string;
  label: string;
  tone: BarTone;
}

export interface BarDay {
  /** `YYYY-MM-DD`, UTC. */
  date: string;
  counts: Record<string, number>;
}

export interface BarChartProps {
  days: BarDay[];
  /** The series that are drawn, in order. */
  series: BarSeries[];
  /** Series that appear only in the hidden table (the comments of the spread chart). */
  tableOnly?: { key: string; label: string }[];
  /** One day carries a small mark and the legend word `markerLabel` (the verdict day). */
  markerDate?: string;
  markerLabel?: string;
  summary: string;
  caption: string;
  /** Shown instead of the bars' legend when nothing is drawn at all. */
  emptyNote?: string;
  className?: string;
}

/** The smallest "round" number (1, 2, 5, 10, 20, 50 …) that is at least `value`. */
export function niceMax(value: number): number {
  if (!(value > 1)) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 5, 10]) {
    if (step * power >= value) return step * power;
  }
  return 10 * power;
}

/**
 * Grouped bars per day, built from HTML (Stitch b3's "Exhibit A", re-purposed). Heights are a
 * percentage of a rounded-up maximum; a day with nothing draws no bar, and a chart with nothing
 * at all says so. No animation.
 */
export function BarChart({
  days,
  series,
  tableOnly = [],
  markerDate,
  markerLabel,
  summary,
  caption,
  emptyNote = "Nothing yet.",
  className,
}: BarChartProps) {
  const drawn = days.flatMap((day) => series.map((s) => day.counts[s.key] ?? 0));
  const largest = Math.max(0, ...drawn);
  const top = niceMax(largest);
  const empty = largest === 0;
  const middle = days.length > 2 ? days[Math.floor((days.length - 1) / 2)] : undefined;
  const columns = ["Day", ...series.map((s) => s.label), ...tableOnly.map((s) => s.label)];
  const rows = days.map((day) => [
    formatShortDate(day.date),
    ...series.map((s) => day.counts[s.key] ?? 0),
    ...tableOnly.map((s) => day.counts[s.key] ?? 0),
  ]);
  return (
    <figure className={cn("flex flex-col gap-space-sm", className)}>
      <div role="img" aria-label={summary} className="flex flex-col gap-space-xs">
        <div className="flex gap-space-xs">
          <div className="flex h-32 flex-col justify-between font-label-code text-label-badge text-outline">
            <span>{top}</span>
            <span>0</span>
          </div>
          <div className="relative h-32 min-w-0 flex-1 border-b border-outline-variant">
            <div className="absolute inset-x-0 top-0 border-t border-dashed border-outline-variant/50" />
            <div className="absolute inset-0 flex items-end gap-px">
              {days.map((day) => (
                <div
                  key={day.date}
                  className="flex h-full min-w-0 flex-1 items-end justify-center gap-px"
                >
                  {series.map((s) => {
                    const n = day.counts[s.key] ?? 0;
                    return n > 0 ? (
                      <div
                        key={s.key}
                        className={cn("w-full max-w-3 rounded-lg", FILL[s.tone])}
                        style={{ height: `${Math.max(3, (n / top) * 100)}%` }}
                      />
                    ) : null;
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="flex gap-space-xs">
          <div className="invisible font-label-code text-label-badge">{top}</div>
          <div className="flex h-2 min-w-0 flex-1 gap-px">
            {days.map((day) => (
              <div key={day.date} className="flex min-w-0 flex-1 justify-center">
                {markerDate === day.date && (
                  <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-on-surface" />
                )}
              </div>
            ))}
          </div>
        </div>
        <div className="flex gap-space-xs font-label-code text-label-badge text-outline">
          <div className="invisible">{top}</div>
          <div className="flex min-w-0 flex-1 justify-between">
            <span>{days[0] ? formatShortDate(days[0].date) : ""}</span>
            <span>{middle ? formatShortDate(middle.date) : ""}</span>
            <span>{days.length > 1 ? formatShortDate(days[days.length - 1].date) : ""}</span>
          </div>
        </div>
        <ul className="flex flex-wrap gap-x-space-lg gap-y-space-xs font-label-code text-label-badge text-on-surface-variant">
          {series.map((s) => (
            <li key={s.key} className="flex items-center gap-space-xs">
              <span aria-hidden="true" className={cn("h-2 w-2 rounded-full", FILL[s.tone])} />
              {s.label}
            </li>
          ))}
          {markerDate && markerLabel && (
            <li className="flex items-center gap-space-xs">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-on-surface" />
              {markerLabel}
            </li>
          )}
        </ul>
        {empty && <p className="font-body-sm text-body-sm text-on-surface-variant">{emptyNote}</p>}
      </div>
      <p className="font-label-code text-label-badge text-outline">{caption}</p>
      <ChartTable caption={caption} columns={columns} rows={rows} />
    </figure>
  );
}
