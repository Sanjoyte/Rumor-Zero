import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export interface ToggleProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "role" | "size" | "onChange"
> {
  /** The accessible name, for example "Toggle Emergency Mode". */
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  /** Colour of the on state: Protocol Blue by default, Emergency Violet for the emergency toggle. */
  tone?: "secondary" | "tertiary";
}

const ON_TONE = {
  secondary: "peer-checked:bg-secondary",
  tertiary: "peer-checked:bg-tertiary",
} as const;

/** Stitch b2 switch. The whole track is the label, so a click anywhere on it toggles. */
export function Toggle({
  label,
  checked,
  onCheckedChange,
  tone = "secondary",
  className,
  disabled,
  ...rest
}: ToggleProps) {
  return (
    <label
      className={cn(
        "relative inline-flex shrink-0 items-center",
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
        className,
      )}
    >
      <input
        {...rest}
        type="checkbox"
        role="switch"
        aria-label={label}
        checked={checked}
        disabled={disabled}
        onChange={(event) => onCheckedChange(event.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden="true"
        className={cn(
          "h-5 w-9 rounded-full bg-surface-container-highest",
          ON_TONE[tone],
          "peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-secondary",
          "after:absolute after:top-[2px] after:left-[2px] after:h-4 after:w-4 after:rounded-full after:border after:border-outline-variant after:bg-surface-container-lowest after:shadow-sm after:transition-all after:content-['']",
          "peer-checked:after:translate-x-full peer-checked:after:border-surface-container-lowest",
        )}
      />
    </label>
  );
}
