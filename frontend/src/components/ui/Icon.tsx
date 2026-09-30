import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

/** The sizes DESIGN.md allows for icons (rem): 0.75, 0.875, 1, 1.125, 1.25, 1.5, 2. */
const SIZE = {
  xs: "text-[0.75rem]",
  sm: "text-[0.875rem]",
  md: "text-[1rem]",
  lg: "text-[1.125rem]",
  xl: "text-[1.25rem]",
  "2xl": "text-[1.5rem]",
  "3xl": "text-[2rem]",
} as const;

export type IconSize = keyof typeof SIZE;

export interface IconProps extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  /** Material Symbols Outlined glyph name, e.g. "check_circle". */
  name: string;
  size?: IconSize;
  /** Solid glyph (FILL 1), used for the verified seal, bolt and similar. */
  filled?: boolean;
  /** Accessible name. Without it the icon is decorative and hidden from assistive tech. */
  label?: string;
}

export function Icon({ name, size = "md", filled, label, className, ...rest }: IconProps) {
  return (
    <span
      {...rest}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn(
        "material-symbols-outlined",
        SIZE[size],
        filled && "[font-variation-settings:'FILL'_1]",
        className,
      )}
    >
      {name}
    </span>
  );
}
