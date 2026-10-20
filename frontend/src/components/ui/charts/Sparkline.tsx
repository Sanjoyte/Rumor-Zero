import { cn } from "@/lib/cn";
import { ChartTable } from "./ChartTable";
import { sparklinePath } from "./sparkline-path";

const WIDTH = 112;
const HEIGHT = 24;
const PAD = 3;

export interface SparklineProps {
  values: number[];
  summary: string;
  table: { caption: string; columns: string[]; rows: (string | number)[][] };
  className?: string;
}

/** A small line chart with an end dot (Stitch b4's sparkline). Neutral, drawn in `currentColor`. */
export function Sparkline({ values, summary, table, className }: SparklineProps) {
  const { d, last } = sparklinePath(values, WIDTH, HEIGHT, PAD);
  return (
    <figure className={cn("flex flex-col", className)}>
      <div role="img" aria-label={summary} className="text-on-surface-variant">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="h-6 w-28"
          aria-hidden="true"
          focusable="false"
        >
          {d && (
            <path
              d={d}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
          {last && <circle cx={last.x} cy={last.y} r="2" className="fill-current" />}
        </svg>
      </div>
      <ChartTable caption={table.caption} columns={table.columns} rows={table.rows} />
    </figure>
  );
}
