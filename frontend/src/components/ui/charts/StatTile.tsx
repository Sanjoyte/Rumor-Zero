import { cn } from "@/lib/cn";

export interface StatTileProps {
  label: string;
  value: string;
  /** A short line under the value ("+10 points"). */
  sub?: string;
  className?: string;
}

/** One number with its name (Stitch b3's tiles). Plain text, so it needs no image role. */
export function StatTile({ label, value, sub, className }: StatTileProps) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-space-xs rounded-lg border border-outline-variant/30 bg-surface-container-low p-space-md",
        className,
      )}
    >
      <p className="font-label-code text-label-badge tracking-wider text-outline uppercase">
        {label}
      </p>
      <p className="font-label-metric text-headline-sm break-words text-on-surface">{value}</p>
      {sub && <p className="font-body-sm text-body-sm text-on-surface-variant">{sub}</p>}
    </div>
  );
}
