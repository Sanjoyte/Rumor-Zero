import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "div" | "article" | "section" | "aside";
  /** Hairline border darkens on hover, for cards that open something (Stitch b1, b4). */
  interactive?: boolean;
}

/** Bordered white card. Position is relative so a VerdictStripe can sit on its left edge. */
export function Card({ as: Tag = "div", interactive, className, ...rest }: CardProps) {
  return (
    <Tag
      {...rest}
      className={cn(
        "relative overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-lowest shadow-sm",
        interactive && "transition-all hover:border-outline/50",
        className,
      )}
    />
  );
}
