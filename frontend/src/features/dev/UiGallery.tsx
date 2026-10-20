"use client";

import { DisplaySections } from "./DisplaySections";
import { FormSections } from "./FormSections";
import { LogoSection } from "./LogoSection";
import { StitchSections } from "./StitchSections";

const LINKS = [
  ["icons", "Icon"],
  ["buttons", "Button"],
  ["fields", "Fields"],
  ["choices", "Choices"],
  ["navigation", "Tabs and chips"],
  ["badges", "Badges"],
  ["avatars", "Avatar"],
  ["logo", "Logo"],
  ["feedback", "Feedback"],
  ["charts", "Charts"],
  ["password-meter", "Password meter"],
  ["danger", "DangerZone"],
  ["stitch-post-cards", "b1 PostCard"],
  ["stitch-stats", "b3 stats"],
  ["stitch-credibility", "Credibility"],
  ["stitch-search", "b4 search"],
  ["stitch-signup", "a2 sign-up"],
  ["stitch-modals", "b2 and d1 modals"],
] as const;

/** Development-only catalogue of every UI primitive in every state (route /dev/ui). */
export function UiGallery() {
  return (
    <main className="mx-auto max-w-wide space-y-space-xl px-space-lg py-space-xl">
      <header className="space-y-space-sm">
        <h1 className="font-headline-lg text-headline-lg text-on-surface">UI gallery</h1>
        <p className="max-w-2xl font-body-md text-body-md text-on-surface-variant">
          Every primitive in every state. This page exists only in development and returns 404 in a
          production build. The app shell has its own preview at{" "}
          <a href="/dev/shell" className="font-medium text-secondary hover:underline">
            /dev/shell
          </a>
          .
        </p>
        <nav aria-label="Gallery sections" className="flex flex-wrap gap-x-space-lg gap-y-space-xs">
          {LINKS.map(([id, label]) => (
            <a
              key={id}
              href={`#${id}`}
              className="font-body-sm text-body-sm font-medium text-secondary hover:underline"
            >
              {label}
            </a>
          ))}
        </nav>
      </header>
      <FormSections />
      <DisplaySections />
      <LogoSection />
      <StitchSections />
    </main>
  );
}
