import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

export interface EmptyStateProps {
  icon: string;
  title: string;
  children?: ReactNode;
  /** A button or link, for example a call to action. */
  action?: ReactNode;
  /** The success tone tints the glyph Verified teal, for all-caught-up moments. */
  tone?: "neutral" | "success";
  className?: string;
}

/** Centred glyph, title and one line of text (Stitch b1 end-of-feed state). */
export function EmptyState({
  icon,
  title,
  children,
  action,
  tone = "neutral",
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-space-md py-12 text-center text-on-surface",
        className,
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-lg border border-outline-variant/40 bg-surface-container-high",
          tone === "success" ? "text-primary" : "text-outline",
        )}
      >
        <Icon name={icon} size="xl" />
      </div>
      <h3 className="font-headline-sm text-headline-sm tracking-tight text-on-surface">{title}</h3>
      {children && <p className="max-w-md font-body-sm text-body-sm text-outline">{children}</p>}
      {action}
    </div>
  );
}
