import type { ReactNode } from "react";

/** Stand-in content for a route whose real screen arrives in a later part. */
export function Placeholder({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg">
      <h1 className="font-headline-lg text-headline-lg text-on-surface">{title}</h1>
      <p className="font-body-md text-body-md text-on-surface-variant">
        {children ?? "This page is coming soon."}
      </p>
    </div>
  );
}
