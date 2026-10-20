import { cn } from "@/lib/cn";
import { ChartTable } from "./ChartTable";

export type MeterTone = "primary" | "error" | "neutral";

const FILL: Record<MeterTone, string> = {
  primary: "bg-primary",
  error: "bg-error",
  neutral: "bg-on-surface-variant",
};

export interface MeterBarProps {
  /** 0 to 100; anything else is clamped. */
  value: number;
  tone?: MeterTone;
  /** Where the line is drawn (0 to 100), for example the auto-label threshold. */
  threshold?: number;
  thresholdLabel?: string;
  /** The graphic's name for a screen reader: the numbers in a sentence. */
  summary: string;
  /** The hidden table: [measure, value] pairs. */
  table: { caption: string; rows: [string, string][] };
  className?: string;
}

const clamp = (n: number) => Math.min(100, Math.max(0, Number.isFinite(n) ? n : 0));

/**
 * A horizontal meter with an optional threshold tick (Stitch b3's gauge, cut to what exists). No
 * animation. The graphic is an image with a summary; the table beside it holds the numbers.
 */
export function MeterBar({
  value,
  tone = "primary",
  threshold,
  thresholdLabel,
  summary,
  table,
  className,
}: MeterBarProps) {
  const fill = clamp(value);
  const tick = threshold === undefined ? null : clamp(threshold);
  // Keep the caption inside the card: it is centred on the tick except near the ends.
  const captionAt = tick === null ? 0 : Math.min(88, Math.max(12, tick));
  return (
    <figure className={cn("flex flex-col gap-space-xs", className)}>
      <div role="img" aria-label={summary} className="flex flex-col gap-space-xs">
        {tick !== null && thresholdLabel && (
          <div className="relative h-4 font-label-code text-label-badge text-on-surface-variant">
            <span
              className="absolute -translate-x-1/2 whitespace-nowrap"
              style={{ left: `${captionAt}%` }}
            >
              {thresholdLabel}
            </span>
          </div>
        )}
        <div className="relative h-3 w-full rounded-full bg-surface-container-highest">
          <div className={cn("h-3 rounded-full", FILL[tone])} style={{ width: `${fill}%` }} />
          {tick !== null && (
            <div
              className="absolute -top-1 -bottom-1 w-0.5 -translate-x-1/2 rounded-full bg-on-surface"
              style={{ left: `${tick}%` }}
            />
          )}
        </div>
        <div className="flex justify-between font-label-code text-label-badge text-outline">
          <span>0%</span>
          <span>100%</span>
        </div>
      </div>
      <ChartTable caption={table.caption} columns={["Measure", "Value"]} rows={table.rows} />
    </figure>
  );
}
