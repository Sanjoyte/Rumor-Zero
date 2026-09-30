import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

export interface DangerZoneProps {
  title?: string;
  /** Small caps tag on the right (Stitch c2 shows CRITICAL EVENT). */
  tag?: string;
  children: ReactNode;
  className?: string;
}

/** Red-tinted card around irreversible account actions (Stitch c2). */
export function DangerZone({ title = "Danger zone", tag, children, className }: DangerZoneProps) {
  return (
    <section
      className={cn(
        "space-y-space-md rounded-lg border border-error/30 bg-error/5 p-space-md",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-space-md">
        <h3 className="flex items-center gap-space-xs font-body-sm text-body-sm font-semibold text-error">
          <Icon name="warning" className="text-error" />
          {title}
        </h3>
        {tag && (
          <span className="font-label-code text-label-badge font-bold tracking-wider text-error uppercase">
            {tag}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

/** One row inside a DangerZone: what the action does on the left, its button on the right. */
export function DangerAction({
  title,
  description,
  action,
}: {
  title: string;
  description: ReactNode;
  action: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-space-md pt-space-xs">
      <div>
        <p className="font-body-sm text-body-sm font-semibold text-on-surface">{title}</p>
        <p className="max-w-xl font-body-sm text-body-sm text-outline">{description}</p>
      </div>
      {action}
    </div>
  );
}
