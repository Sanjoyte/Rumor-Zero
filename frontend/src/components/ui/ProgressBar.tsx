import { cn } from "@/lib/cn";

export type ProgressTone = "primary" | "secondary" | "error" | "verdict-review" | "tertiary";

const FILL: Record<ProgressTone, string> = {
  primary: "bg-primary",
  secondary: "bg-secondary",
  error: "bg-error",
  "verdict-review": "bg-verdict-review",
  tertiary: "bg-tertiary",
};

export interface ProgressBarProps {
  /** 0 to 100. Out-of-range values are clamped. */
  value: number;
  label: string;
  tone?: ProgressTone;
  className?: string;
}

/** Thin progress track with a coloured fill (Stitch c2 and b3). */
export function ProgressBar({ value, label, tone = "primary", className }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, Number.isFinite(value) ? value : 0));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className={cn(
        "h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest",
        className,
      )}
    >
      <div className={cn("h-1.5 rounded-full", FILL[tone])} style={{ width: `${clamped}%` }} />
    </div>
  );
}
