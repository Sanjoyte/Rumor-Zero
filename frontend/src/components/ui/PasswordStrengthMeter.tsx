import { cn } from "@/lib/cn";
import { PASSWORD_STRENGTH_LABELS, type PasswordStrength } from "@/lib/password-strength";

const FILL: Record<PasswordStrength, string> = {
  0: "bg-surface-container-highest",
  1: "bg-error",
  2: "bg-verdict-review",
  3: "bg-primary",
  4: "bg-primary",
};

const LABEL_COLOR: Record<PasswordStrength, string> = {
  0: "text-outline",
  1: "text-error",
  2: "text-on-verdict-review",
  3: "text-primary",
  4: "text-primary",
};

/** Four-segment strength bar (Stitch a2 and a6, with one consistent scale). Advisory only. */
export function PasswordStrengthMeter({
  score,
  className,
}: {
  score: PasswordStrength;
  className?: string;
}) {
  return (
    <div className={cn("pt-space-sm", className)}>
      <div aria-hidden="true" className="grid h-1 grid-cols-4 gap-space-xs">
        {[1, 2, 3, 4].map((segment) => (
          <div
            key={segment}
            data-filled={segment <= score}
            className={cn(
              "h-full rounded-full",
              segment <= score ? FILL[score] : "bg-surface-container-highest",
            )}
          />
        ))}
      </div>
      <div className="mt-space-xs flex items-center justify-between font-body-sm text-body-sm text-outline">
        <span>Password strength</span>
        <span aria-live="polite" className={cn("font-medium", LABEL_COLOR[score])}>
          {PASSWORD_STRENGTH_LABELS[score]}
        </span>
      </div>
    </div>
  );
}
