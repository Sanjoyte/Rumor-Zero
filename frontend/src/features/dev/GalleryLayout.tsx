import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Section({
  id,
  title,
  note,
  children,
}: {
  id: string;
  title: string;
  note?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="space-y-space-lg border-t border-outline-variant/30 pt-space-xl">
      <header className="space-y-space-xs">
        <h2 className="font-headline-md text-headline-md text-on-surface">{title}</h2>
        {note && <p className="max-w-2xl font-body-sm text-body-sm text-outline">{note}</p>}
      </header>
      <div className="space-y-space-lg">{children}</div>
    </section>
  );
}

/** One labelled example inside a section. */
export function Specimen({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="space-y-space-xs">
      <p className="font-label-code text-label-code text-outline uppercase">{label}</p>
      <div className={cn("flex flex-wrap items-start gap-space-md", className)}>{children}</div>
    </div>
  );
}
