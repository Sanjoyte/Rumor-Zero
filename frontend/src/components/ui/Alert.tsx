import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

export type AlertTone = "info" | "success" | "warning" | "error" | "neutral";

const TONE: Record<AlertTone, { box: string; icon: string; glyph: string; text: string }> = {
  info: {
    box: "border-secondary/30 bg-secondary/10",
    icon: "text-secondary",
    glyph: "info",
    text: "text-on-surface-variant",
  },
  success: {
    box: "border-primary/30 bg-primary/10",
    icon: "text-primary",
    glyph: "check_circle",
    text: "text-on-surface-variant",
  },
  warning: {
    box: "border-verdict-review/30 bg-verdict-review/10",
    icon: "text-on-verdict-review",
    glyph: "warning",
    text: "text-on-surface-variant",
  },
  error: {
    box: "border-error/30 bg-error/10",
    icon: "text-error",
    glyph: "error",
    text: "text-error",
  },
  neutral: {
    box: "border-outline-variant/30 bg-surface-container-low",
    icon: "text-outline",
    glyph: "shield",
    text: "text-outline",
  },
};

export interface AlertProps {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
  /** Shows a close button. The parent decides what dismissing means. */
  onDismiss?: () => void;
  className?: string;
}

/** Callout banner (Stitch a3, a4, a5, a6, d1). Errors are announced; the rest are static. */
export function Alert({ tone = "info", title, children, onDismiss, className }: AlertProps) {
  const style = TONE[tone];
  const role = tone === "error" ? "alert" : tone === "success" ? "status" : undefined;
  return (
    <div
      role={role}
      className={cn(
        "flex items-start gap-space-sm rounded-lg border p-space-md font-body-sm text-body-sm",
        style.box,
        style.text,
        className,
      )}
    >
      <Icon name={style.glyph} className={cn("mt-0.5 shrink-0", style.icon)} />
      <div className="min-w-0 flex-1 space-y-0.5">
        {title && (
          <p className={cn("font-semibold", tone === "error" ? "text-error" : "text-on-surface")}>
            {title}
          </p>
        )}
        {children && <div>{children}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          aria-label="Dismiss"
          onClick={onDismiss}
          className="shrink-0 rounded-lg p-0.5 transition-colors hover:text-on-surface"
        >
          <Icon name="close" size="sm" />
        </button>
      )}
    </div>
  );
}
