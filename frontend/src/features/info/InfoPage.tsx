import type { ReactNode } from "react";
import { Alert } from "@/components/ui/Alert";
import { cn } from "@/lib/cn";

/** The reading-width frame of the help and legal pages: one `h1`, then sections. */
export function InfoPage({
  title,
  intro,
  children,
}: {
  title: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  return (
    <article className="mx-auto flex w-full max-w-reading flex-col gap-space-xl px-space-lg py-space-xl">
      <header className="flex flex-col gap-space-md">
        <h1 className="font-headline-lg text-headline-lg text-on-surface">{title}</h1>
        {intro ? (
          <p className="font-body-lg text-body-lg text-on-surface-variant">{intro}</p>
        ) : null}
      </header>
      {children}
    </article>
  );
}

/** A titled block. With an `id` it is a link target (`/how-it-works#credibility`). */
export function Section({
  id,
  title,
  children,
  className,
}: {
  id?: string;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  const headingId = id ? `${id}-heading` : undefined;
  return (
    <section
      id={id}
      aria-labelledby={headingId}
      className={cn("flex scroll-mt-24 flex-col gap-space-md", className)}
    >
      <h2 id={headingId} className="font-headline-md text-headline-md text-on-surface">
        {title}
      </h2>
      {children}
    </section>
  );
}

/** A question and its answer. The question is a heading so it shows in the page outline. */
export function Question({ question, children }: { question: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-space-sm">
      <h3 className="font-headline-sm text-headline-sm text-on-surface">{question}</h3>
      <div className="flex flex-col gap-space-sm font-body-md text-body-md text-on-surface-variant">
        {children}
      </div>
    </div>
  );
}

/** Body text in the pages' reading colour. */
export function P({ children }: { children: ReactNode }) {
  return <p className="font-body-md text-body-md text-on-surface-variant">{children}</p>;
}

/** The marker on text that a lawyer must read before launch (guide §16). */
export function LegalReviewNotice({ children }: { children?: ReactNode }) {
  return (
    <Alert tone="warning" title="Needs legal review">
      {children ?? "This text is a placeholder. It must be reviewed by a lawyer before launch."}
    </Alert>
  );
}
