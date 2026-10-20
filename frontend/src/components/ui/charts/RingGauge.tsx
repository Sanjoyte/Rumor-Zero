import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { ChartTable } from "./ChartTable";

export interface RingGaugeProps {
  /** 0 to 100, or null for "no value yet" (the track only). */
  value: number | null;
  /** What sits in the middle: the number, or "New". */
  centre: ReactNode;
  summary: string;
  table: { caption: string; rows: [string, string][] };
  className?: string;
}

/**
 * A ring that fills clockwise from 12 o'clock (Stitch c1's "Epistemic Standing", whose arc started
 * at 9 o'clock by mistake). Neutral: the track and the arc are both greys. The arc is not drawn for
 * null or 0, because a round cap would paint a dot.
 */
export function RingGauge({ value, centre, summary, table, className }: RingGaugeProps) {
  const arc = value === null || !Number.isFinite(value) ? 0 : Math.min(100, Math.max(0, value));
  return (
    <figure className={cn("flex flex-col", className)}>
      <div role="img" aria-label={summary} className="relative h-24 w-24 shrink-0">
        <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="18"
            cy="18"
            r="15.9155"
            pathLength={100}
            fill="none"
            strokeWidth="3"
            className="stroke-surface-container-highest"
          />
          {arc > 0 && (
            <circle
              cx="18"
              cy="18"
              r="15.9155"
              pathLength={100}
              fill="none"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={`${arc} 100`}
              className="stroke-on-surface-variant"
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          {centre}
        </div>
      </div>
      <ChartTable caption={table.caption} columns={["Measure", "Value"]} rows={table.rows} />
    </figure>
  );
}
